$(document).ready(function () {

    let board;
    let pendingPromotion = null;
    let lastPosition = null;   // NEW - always store before move
    let currentTurn = window.initialTurn || 'white';  // Track whose turn it is
    let isGameOver = false;     // Track if game is over
    let aiThinking = false;     // Track if AI is currently thinking

    // Use initial position from backend, fallback to 'start'
    let initialPosition = window.initialFen || 'start';

    board = Chessboard('board', {
        draggable: true,
        position: initialPosition,
        pieceTheme: '/static/images/chesspieces/wikipedia/{piece}.png',

        onDragStart: function (source, piece) {
            // snapshot BEFORE illegal moves
            lastPosition = board.position();

            // Prevent dragging if game over, AI is thinking, or opponent's pieces
            const pieceColor = piece.startsWith('w') ? 'white' : 'black';
            if (isGameOver || aiThinking || pieceColor !== currentTurn) {
                return false;  // Prevent drag
            }
        },

        onDrop: function (source, target, piece) {

            // Check if piece was dropped on same square it started from
            if (source === target) {
                return 'snapback';  // Return piece to original position
            }

            const promotionCheck = detectPromotion(source, target, piece);

            if (promotionCheck.promotionNeeded) {

                pendingPromotion = { source, target, oldPos: lastPosition };
                board.draggable = false;  // Disable dragging during promotion choice

                showPromotionDialog(function(selectedPiece) {
                    sendMove(pendingPromotion.source, pendingPromotion.target, selectedPiece);
                });

                return;
            }

            sendMove(source, target);
        }
    });

    // Make board available globally for testing
    window.board = board;

    // Initialize UI with backend values
    updateSpecialMove(window.initialSpecialMoves || []);
    updateMoveHistory(window.initialMoveHistory || []);
    updateCaptured(window.initialCapturedPieces || { white: [], black: [] });
    updateMaterialAdvantage(Number(window.initialMaterial) || 0);
    updatePositionEvaluation(Number(window.initialEvaluation) || 0);

    // If it's AI's turn on page load, trigger AI move
    if (currentTurn === 'black' && window.aiEnabled && !isGameOver) {
        aiThinking = true;  // Set AI thinking flag
        board.draggable = false;
        $.post("/ai-move", function(aiResponse) {
            aiThinking = false;  // Clear AI thinking flag
            board.draggable = true;
            board.position(aiResponse.fen);
            currentTurn = aiResponse.turn;
            updateCaptured(aiResponse.captured_pieces);
            updateMaterialAdvantage(aiResponse.material);
            updatePositionEvaluation(aiResponse.evaluation);
            updateMoveHistory(aiResponse.move_history);
            updateStatus(
                aiResponse.turn,
                aiResponse.check,
                aiResponse.checkmate,
                aiResponse.stalemate,
                false,
                false,
                false,
                aiResponse.game_over
            );
        });
    }

    // Send move to server
    function sendMove(source, target, promotionPiece=null) {

        board.draggable = false;  // Disable dragging during move

        // Show "AI is thinking..." immediately since we're about to send a player move
        // (which will trigger AI response if legal)
        updateStatus('black', false, false, false, false, false, false, false);

        const payload = { from: source, to: target };
        if (promotionPiece) payload.promotion = promotionPiece;

        $.ajax({
            url: "/move",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify(payload),

            success: function (response) {

                // Handle response based on outcome
                if (response.status === "ok") {

                    pendingPromotion = null;

                    board.position(response.fen);
                    currentTurn = response.turn;  // Update current turn
                    isGameOver = response.game_over;  // Update game over status
                    updateStatus(response.turn, response.check, response.checkmate, response.stalemate, response.fifty_moves, response.repetition, response.insufficient_material, response.game_over);
                    updateSpecialMove(response.special_moves);
                    updateMoveHistory(response.move_history);
                    updateCaptured(response.captured_pieces);
                    updateMaterialAdvantage(response.material);
                    updatePositionEvaluation(response.evaluation);
                    updateErrorMessage("");  // Clear any previous error

                    // If it's now black's turn, trigger AI move
                    if (response.turn === "black" && !response.game_over) {
                        // Keep aiThinking = true, board.draggable = false
                        $.post("/ai-move", function(aiResponse) {
                            aiThinking = false;  // Clear AI thinking flag
                            board.draggable = true;  // Re-enable dragging after AI move
                            board.position(aiResponse.fen);
                            currentTurn = aiResponse.turn;
                            updateCaptured(aiResponse.captured_pieces);
                            updateMaterialAdvantage(aiResponse.material);
                            updatePositionEvaluation(aiResponse.evaluation);
                            updateMoveHistory(aiResponse.move_history);
                            updateStatus(
                                aiResponse.turn,
                                aiResponse.check,
                                aiResponse.checkmate,
                                aiResponse.stalemate,
                                false,
                                false,
                                false,
                                aiResponse.game_over
                            );
                        });
                    } else {
                        // It's still player's turn or game over, re-enable interaction
                        aiThinking = false;
                        board.draggable = true;
                    }

                } else {

                    // Illegal move - re-enable interaction
                    aiThinking = false;
                    board.draggable = true;
                    rollbackPosition();   // unified rollback
                    // 🔧 FIX: Use server's detailed error message if available
                    const errorMsg = response.message || "Illegal move!";
                    updateErrorMessage(errorMsg);
                    // Restore correct turn status after illegal move
                    updateStatus(currentTurn, false, false, false, false, false, false, false);
                }
            },

            error: function(xhr) {
                // Error - re-enable interaction
                aiThinking = false;
                board.draggable = true;
                rollbackPosition();
                // 🔧 FIX: Extract error message from server response
                const errorMsg = xhr.responseJSON && xhr.responseJSON.message 
                    ? xhr.responseJSON.message 
                    : "Server error";
                updateErrorMessage(errorMsg);
                // Restore correct turn status after server error
                updateStatus(currentTurn, false, false, false, false, false, false, false);
            }
        });

        // Immediately disable interaction after sending move request
        aiThinking = true;
        board.draggable = false;
    }

    // Make sendMove available globally for testing
    window.sendMove = sendMove;

    // properly undo illegal moves
    function rollbackPosition() {

        if (pendingPromotion) {
            board.position(pendingPromotion.oldPos);
            pendingPromotion = null;
        } else if (lastPosition) {
            board.position(lastPosition);
        }
    }

    function detectPromotion(source, target, piece) {
        // Only pawns
        if (piece[1] !== 'P') {
            return { promotionNeeded: false };
        }

        const isWhite = piece.startsWith('w');
        const finalRank = isWhite ? "8" : "1";

        // Must land on final rank
        if (!target.endsWith(finalRank)) {
            return { promotionNeeded: false };
        }

        const sourceFile = source[0];
        const targetFile = target[0];
        
        // Get current board position to validate move
        const position = board.position();

        // Pawn moving diagonally — capture move
        if (sourceFile !== targetFile) {
            // Check if target has opponent piece
            const targetPiece = position[target];
            if (!targetPiece || targetPiece[0] === piece[0]) {
                // No piece or same color - invalid diagonal move
                return { promotionNeeded: false };
            }
            // Valid capture to last rank - needs promotion
            return { promotionNeeded: true };
        }

        // Straight pawn move to last rank
        // Check if target square is empty
        if (position[target]) {
            // Target occupied - illegal move, don't show promotion dialog
            return { promotionNeeded: false };
        }

        // Valid straight move to last rank → promotion
        return { promotionNeeded: true };
    }

    // Make detectPromotion available globally for testing
    window.detectPromotion = detectPromotion;

    function showPromotionDialog(callback) {

        $("#promotion-dialog").remove();

        const html = `
        <div id="promotion-dialog">
            <p class="promotion-title">Promote pawn to:</p>

            <div class="promotion-options">
                <button class="promote" data-piece="q">Queen</button>
                <button class="promote" data-piece="r">Rook</button>
                <button class="promote" data-piece="b">Bishop</button>
                <button class="promote" data-piece="n">Knight</button>
            </div>

            <button id="cancel-promotion" class="promotion-cancel">Cancel</button>
        </div>`;

        $("body").append(html);

        $(".promote").click(function () {
            const selectedPiece = $(this).data("piece");
            $("#promotion-dialog").remove();
            callback(selectedPiece);
        });

        $("#cancel-promotion").click(function () {
            $("#promotion-dialog").remove();
            board.draggable = true;
            rollbackPosition();
        });
    }

    // Make showPromotionDialog available globally for testing
    window.showPromotionDialog = showPromotionDialog;

    $("#reset-btn").click(function () {
        $.post("/reset", function(response) {
            if (response.status === "ok") {
                pendingPromotion = null;
                lastPosition = null;
                currentTurn = 'white';  // Reset to white's turn
                isGameOver = false;      // Reset game over status
                board.start();
                updateStatus('white', false, false, false, false, false, false, false);
                updateSpecialMove(response.special_moves);
                updateMoveHistory([]);
                updateCaptured({ white: [], black: [] });
                updateErrorMessage("");  // Clear error on reset
                updateMaterialAdvantage(0);
                updatePositionEvaluation(0);
            }
        });
    });

    function updateStatus(turn, check, checkmate, stalemate, fifty_moves, repetition, insufficient_material, game_over) {
        let status;
        if (checkmate) {
            status = turn === 'white' ? "Black wins — Checkmate!" : "White wins — Checkmate!";
        } else if (stalemate || fifty_moves || repetition || insufficient_material) {
            status = "Draw";
        } else {
            if (turn === 'white') {
                status = "White's turn";
            } else {
                status = "AI is thinking...";
            }
            if (check) status += " - Check!";
        }
        $("#game-status").text(status);
    }

    function updateSpecialMove(special_moves) {
        const whiteList = $("#special-white");
        const blackList = $("#special-black");

        whiteList.empty();
        blackList.empty();

        if (!Array.isArray(special_moves)) return;

        special_moves.forEach(move => {
            // Expected formats:
            // "White: O-O"
            // "Black: e8=Q"
            // or fallback: infer by prefix

            let color = null;
            let text = move;

            if (move.startsWith("White")) {
                color = "white";
                text = move.replace(/^White:\s*/i, "");
            } else if (move.startsWith("Black")) {
                color = "black";
                text = move.replace(/^Black:\s*/i, "");
            }

            const li = $("<li>").text(text);

            if (color === "white") {
                whiteList.append(li);
            } else if (color === "black") {
                blackList.append(li);
            } else {
                // Fallback: if color unknown, put in both or skip
                whiteList.append(li);
            }
        });
    }

    // Make updateSpecialMove available globally for testing
    window.updateSpecialMove = updateSpecialMove;

    function updateErrorMessage(message) {
        $("#error-message").text(message);
    }

    function updateMoveHistory(history) {
        if (!Array.isArray(history)) return;

        const tbody = $("#move-history tbody");
        tbody.empty();

        for (let i = 0; i < history.length; i += 2) {
            const moveNumber = Math.floor(i / 2) + 1;
            const whiteMove = history[i] || "";
            const blackMove = history[i + 1] || "";

            const row = `
                <tr>
                    <td>${moveNumber}</td>
                    <td>${whiteMove}</td>
                    <td>${blackMove}</td>
                </tr>
            `;

            tbody.append(row);
        }

        // Auto-scroll to latest move
        tbody.scrollTop(tbody.prop("scrollHeight"));
    }

    function updateCaptured(captured) {
        if (!captured || !captured.white || !captured.black) return;

        renderCapturedRow("#white-captured", captured.white);
        renderCapturedRow("#black-captured", captured.black);
    }

    function renderCapturedRow(selector, pieces) {
        const container = $(selector);
        container.empty();

        // Determine piece color based on which tray we're rendering
        const isWhiteTray = selector === "#black-captured"; // white pieces captured by black
        const colorPrefix = isWhiteTray ? "w" : "b";

        pieces.forEach(piece => {
            let pieceCode = piece;

            // If backend sends single-letter piece (p, n, q, etc)
            if (piece.length === 1) {
                pieceCode = colorPrefix + piece.toUpperCase();
            }

            const img = $("<img>", {
                src: `/static/images/chesspieces/wikipedia/${pieceCode}.png`,
                alt: pieceCode,
                class: "captured-piece"
            });

            container.append(img);
        });
    }

    function updateMaterialAdvantage(material) {
        const el = $("#material-advantage");

        if (material === 0) {
            el
            .text("Even")
            .removeClass("material-white material-black");
            return;
        }

        const pawns = Math.abs(material / 100).toFixed(1);

        if (material > 0) {
            el
            .text(`White +${pawns}`)
            .removeClass("material-black")
            .addClass("material-white");
        } else {
            el
            .text(`Black +${pawns}`)
            .removeClass("material-white")
            .addClass("material-black");
        }
    }

    // Make updateMaterialAdvantage available globally for testing
    window.updateMaterialAdvantage = updateMaterialAdvantage;

    function updatePositionEvaluation(evalCp) {
        const el = $("#position-eval");

        if (evalCp === 0 || evalCp === null || evalCp === undefined) {
            el.text("≈ 0.0 (Equal)");
            return;
        }

        const pawns = (evalCp / 100).toFixed(2);
        const label = formatEvaluation(evalCp);

        el.text(`${pawns} (${label})`);
    }

    // Make updatePositionEvaluation available globally for testing
    window.updatePositionEvaluation = updatePositionEvaluation;

    function formatEvaluation(evalCp) {
        const abs = Math.abs(evalCp);

        if (abs < 30) {
            return "Equal";
        }

        if (evalCp > 0) {
            if (abs >= 300) return "White Winning";
            if (abs >= 120) return "White Better";
            return "White Slightly Better";
        } else {
            if (abs >= 300) return "Black Winning";
            if (abs >= 120) return "Black Better";
            return "Black Slightly Better";
        }
    }

    // Handle window resize fore responsiveness

    let resizeTimeout;

    function resizeBoardSafely() {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            if (board) {
                board.resize();
            }
        }, 250); // mobile browsers need time to settle layout
    }

    window.addEventListener("resize", resizeBoardSafely);
    window.addEventListener("orientationchange", resizeBoardSafely);

    // tap-to-move for mobile (server-authoritative)
    let selectedSquare = null;

    function onSquareTap(square) {

        if (currentTurn !== "white" || isGameOver || aiThinking) return;

        const position = board.position();
        const piece = position[square];

        // FIRST TAP — select piece
        if (!selectedSquare) {

            // Must tap a white piece
            if (!piece || !piece.startsWith("w")) return;

            selectedSquare = square;
            highlightSquare(square);
            return;
        }

        // SECOND TAP — attempt move
        clearHighlights();

        // Cancel if same square tapped
        if (square === selectedSquare) {
            selectedSquare = null;
            return;
        }

        sendMove(selectedSquare, square);
        selectedSquare = null;
    }

    function highlightSquare(square) {
        clearHighlights();
        const el = document.querySelector(`[data-square="${square}"]`);
        if (el) el.style.background = "rgba(37, 99, 235, 0.35)";
    }

    function clearHighlights() {
        document.querySelectorAll("[data-square]").forEach(el => {
            el.style.background = "";
        });
    }

    // Attach handler (robust)
    document.getElementById("board").addEventListener("click", (e) => {
        const squareEl = e.target.closest("[data-square]");
        if (!squareEl) return;
        onSquareTap(squareEl.dataset.square);
    });

    //resign
    $("#resign-btn").click(function () {
        $.ajax({
            url: "/resign",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({ color: currentTurn }),
            success: function (response) {
                if (response.status === "ok") {
                    updateStatus(
                        null,
                        false,
                        false,
                        false,
                        false,
                        false,
                        false,
                        true
                    );

                    $("#game-status").text(
                        `${response.winner.charAt(0).toUpperCase() + response.winner.slice(1)} wins — resignation`
                    );
                    isGameOver = true;
                    board.draggable = false;
                }
            }
        });
    });
});