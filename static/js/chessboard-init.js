$(document).ready(function () {

    const config = window.CHESS_CONFIG || {};
    const playerColor = "white"; // later this comes from auth/session

    let board;
    let pendingPromotion = null;
    let lastPosition = null;
    let currentTurn = config.turn || 'white';
    let isGameOver = false;
    let aiThinking = false;
    let aiInFlight = false;
    let moveInFlight = false;

    // Use initial position from backend, fallback to 'start'
    let initialPosition = config.fen || 'start';

    //get the ai's record
    function loadAIRecord() {
        $.get("/stats/ai-record", function (data) {
            $("#ai-wins").text(data.wins);
            $("#ai-losses").text(data.losses);
            $("#ai-draws").text(data.draws);
            $("#ai-winrate").text(`${data.win_rate}%`);
        });
    }

    //load the record
    loadAIRecord();

    board = Chessboard('board', {
        draggable: true,
        position: initialPosition,
        pieceTheme: '/static/images/chesspieces/wikipedia/{piece}.png',

        onDragStart: function (source, piece) {

            if (!canHumanMove()) {
                return false;
            }

            const pieceColor = piece.startsWith('w') ? 'white' : 'black';
            if (pieceColor !== currentTurn) {
                return false;
            }

            lastPosition = board.position();
        },

        onDrop: function (source, target, piece) {

            if (source === target) {
                return 'snapback';
            }

            const promotionCheck = detectPromotion(source, target, piece);

            if (promotionCheck.promotionNeeded) {

                moveInFlight = true; 
                pendingPromotion = { source, target, oldPos: lastPosition };
                board.draggable = false;

                showPromotionDialog(function(selectedPiece) {
                    sendMove(pendingPromotion.source, pendingPromotion.target, selectedPiece);
                });

                return;
            }

            sendMove(source, target);
        }
    });

    window.board = board;

    // Initialize UI with backend values
    updateFromState(config);

    // 🔑 INITIALIZE BUTTON VISIBILITY - Hide New Game, show Resign/Draw on page load
    // Only hide reset if game is active (not game over)
    const initialGameState = config.gameOver ? 'game_over' : 'game_active';
    updateButtonVisibility(initialGameState);

    // If it's AI's turn on page load, trigger AI move
    maybeTriggerAiTurn({turn: currentTurn, game_over: isGameOver});

    // Send move to server
    function sendMove(source, target, promotionPiece=null) {

        if (!canHumanMove()) return;

        moveInFlight = true;
        board.draggable = false;

        $("#game-status").text("Processing move…");

        const payload = { from: source, to: target };
        if (promotionPiece) payload.promotion = promotionPiece;

        $.ajax({
            url: "/move",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify(payload),

            success: function (response) {
                moveInFlight = false;

                if (response.status === "ok") {

                    pendingPromotion = null;
                    updateErrorMessage("");

                    updateFromState(response);          
                    maybeTriggerAiTurn(response);

                } else {

                    aiThinking = false;
                    board.draggable = true;
                    rollbackPosition();
                    const errorMsg = response.message || "Illegal move!";
                    updateErrorMessage(errorMsg);
                    updateStatus(currentTurn, false, false, false, false, false, false, false);
                }
            },

            error: function(xhr) {
                moveInFlight = false;
                aiThinking = false;
                board.draggable = true;
                rollbackPosition();
                const errorMsg = xhr.responseJSON && xhr.responseJSON.message 
                    ? xhr.responseJSON.message 
                    : "Server error";
                updateErrorMessage(errorMsg);
                updateStatus(currentTurn, false, false, false, false, false, false, false);
            }
        });

    }

    window.sendMove = sendMove;

    function rollbackPosition() {

        if (pendingPromotion) {
            board.position(pendingPromotion.oldPos);
            pendingPromotion = null;
        } else if (lastPosition) {
            board.position(lastPosition);
        }
    }

    function detectPromotion(source, target, piece) {
        if (piece[1] !== 'P') {
            return { promotionNeeded: false };
        }

        const isWhite = piece.startsWith('w');
        const finalRank = isWhite ? "8" : "1";

        if (!target.endsWith(finalRank)) {
            return { promotionNeeded: false };
        }

        const sourceFile = source[0];
        const targetFile = target[0];
        
        const position = board.position();

        if (sourceFile !== targetFile) {
            const targetPiece = position[target];
            if (!targetPiece || targetPiece[0] === piece[0]) {
                return { promotionNeeded: false };
            }
            return { promotionNeeded: true };
        }

        if (position[target]) {
            return { promotionNeeded: false };
        }

        return { promotionNeeded: true };
    }

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
            moveInFlight = false; 
            board.draggable = true;
            rollbackPosition();
        });
    }

    window.showPromotionDialog = showPromotionDialog;

    // 🔑 NEW FUNCTION - Controls button visibility based on game state
    function updateButtonVisibility(state) {
        const resetBtn = $("#reset-btn");
        const resignBtn = $("#resign-btn");
        const drawBtn = $("#offer-draw-btn");
        const claim50Btn = $("#claim-50-btn");
        const claimRepBtn = $("#claim-repetition-btn");

        if (state === 'game_active') {
            // Game is active: show New Game, show Resign/Draw
            resetBtn.show();
            resignBtn.show();
            drawBtn.show();
        } else if (state === 'game_over') {
            // Game is over: show New Game, hide Resign/Draw
            resetBtn.show();
            resignBtn.hide();
            drawBtn.hide();
            claim50Btn.hide();
            claimRepBtn.hide();
        }
    }

    $("#reset-btn").click(function () {
        $.post("/reset", function(response) {
            if (response.status === "ok") {
                pendingPromotion = null;
                lastPosition = null;
                aiThinking = false;
                board.draggable = true;

                updateErrorMessage("");
                updateFromState(response);

                updateButtonVisibility('game_active');
            }
        });
    });

    function updateStatus(turn, check, checkmate, stalemate, fifty_moves, can_claim_repetition, insufficient_material, game_over) {
        let status;
        if (checkmate) {
            status = turn === 'white' ? "Black wins — Checkmate!" : "White wins — Checkmate!";
        } else if (stalemate || insufficient_material || game_over) {
            status = "Draw";
        } else if (fifty_moves) {
            status = "50-move rule available";
        } else if (can_claim_repetition) {
            status = "Threefold repetition available";
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

        // Skip processing if not array
        if (!Array.isArray(special_moves)) return;

        // Always clear and repopulate to avoid duplicates
        // (Backend returns complete accumulated list, not just new items)
        whiteList.empty();
        blackList.empty();

        // If array is empty, lists are already cleared - done
        if (special_moves.length === 0) {
            return;
        }

        // Populate lists with all special moves
        special_moves.forEach(move => {
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
                whiteList.append(li);
            }
        });
    }

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

        const isWhiteTray = selector === "#black-captured";
        const colorPrefix = isWhiteTray ? "w" : "b";

        pieces.forEach(piece => {
            let pieceCode = piece;

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

    let resizeTimeout;

    function resizeBoardSafely() {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            if (board) {
                board.resize();
            }
        }, 250);
    }

    window.addEventListener("resize", resizeBoardSafely);
    window.addEventListener("orientationchange", resizeBoardSafely);

    let selectedSquare = null;

    function onSquareTap(square) {

        if (!canHumanMove()) return;

        const position = board.position();
        const piece = position[square];

        if (!selectedSquare) {

            if (!piece || !piece.startsWith("w")) return;

            selectedSquare = square;
            highlightSquare(square);
            return;
        }

        clearHighlights();

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

    document.getElementById("board").addEventListener("click", (e) => {
        const squareEl = e.target.closest("[data-square]");
        if (!squareEl) return;
        onSquareTap(squareEl.dataset.square);
    });

    document.getElementById("board").addEventListener("touchend", (e) => {
        e.preventDefault();
        const squareEl = e.target.closest("[data-square]");
        if (!squareEl) return;
        onSquareTap(squareEl.dataset.square);
    });

    // 🔑 RESIGN BUTTON - Show New Game, hide Resign/Draw on click
    $("#resign-btn").click(function () {
        $.ajax({
            url: "/resign",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({ color: playerColor }),
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

                    // 🔑 After resign: show New Game, hide Resign/Draw
                    updateButtonVisibility('game_over');
                }
            }
        });
    });

    function updateDrawButtons(state) {
        if (!state) return;

        const fiftyBtn = document.getElementById("claim-50-btn");
        if (!fiftyBtn) return;

        fiftyBtn.style.display =
            state.fifty_moves ? "inline-block" : "none";
        
        const repetitionBtn = document.getElementById("claim-repetition-btn");
        if (!repetitionBtn) return;

        repetitionBtn.style.display =
            state.can_claim_repetition ? "inline-block" : "none";
    }

    // 🔑 OFFER DRAW BUTTON - Show New Game, hide Resign/Draw on click
    $("#offer-draw-btn").click(function () {

        if (!canHumanMove()) return;

        $.ajax({
            url: "/draw-agreement",
            type: "POST",
            success: function (response) {
                if (response.status === "ok") {
                    endGameUI("Draw by agreement");
                    
                    // 🔑 After draw: show New Game, hide Resign/Draw
                    updateButtonVisibility('game_over');
                }
            },
            error: function () {
                updateErrorMessage("Unable to offer draw.");
            }
        });  
    });

    // 🔑 CLAIM 50-MOVE DRAW - Show New Game, hide Resign/Draw on claim
    $("#claim-50-btn").click(function () {
        if (!canHumanMove()) return;

        $.post("/claim-draw/50-move", function (response) {
            if (response.status === "ok") {
                endGameUI("Draw by 50-move rule");
                updateButtonVisibility('game_over');
            } else {
                updateErrorMessage(response.message);
            }
        });
    });

    // 🔑 CLAIM REPETITION DRAW - Show New Game, hide Resign/Draw on claim
    $("#claim-repetition-btn").click(function () {
        if (!canHumanMove()) return;

        $.post("/claim-draw/repetition", function (response) {
            if (response.status === "ok") {
                endGameUI("Draw by repetition");
                updateButtonVisibility('game_over');
            } else {
                updateErrorMessage(response.message);
            }
        });
    });

    function endGameUI(message) {
        isGameOver = true;
        board.draggable = false;
        $("#game-status").text(message);
        $("#offer-draw-btn, #claim-50-btn, #claim-repetition-btn").hide();
    }

    // state function
    function updateFromState(state) {
        if (!state) return;

        board.position(state.fen);
        currentTurn = state.turn;
        isGameOver = state.game_over;

        updateStatus(
            state.turn,
            state.check,
            state.checkmate,
            state.stalemate,
            state.fifty_moves,
            state.can_claim_repetition,
            state.insufficient_material,
            state.game_over
        );

        updateDrawButtons(state);
        updateCaptured(state.captured_pieces);
        updateMoveHistory(state.move_history);
        updateSpecialMove(state.special_moves);
        updateMaterialAdvantage(state.material);
        updatePositionEvaluation(state.evaluation);

        if (state.game_over && !isGameOver) {
            board.draggable = false;
            updateButtonVisibility('game_over');
            loadAIRecord();
        }
    }

    // helper for ai turn and board state
    function maybeTriggerAiTurn(state) {
        if (!state || state.game_over) return;

        // Not AI's turn → unlock board
        if (state.turn !== "black") {
            aiThinking = false;
            board.draggable = true;
            return;
        }

        // AI already thinking → do nothing
        if (aiInFlight) return;

        // Lock everything
        aiInFlight = true;
        aiThinking = true;
        board.draggable = false;

        $.post("/ai-move", function (aiResponse) {
            aiInFlight = false;
            aiThinking = false;
            board.draggable = true;

            updateFromState(aiResponse);
        }).fail(function () {
            // Always unlock on failure
            aiInFlight = false;
            aiThinking = false;
            board.draggable = true;
        });
    }

    function canHumanMove() {
        return !isGameOver && !aiThinking && !aiInFlight && !moveInFlight;
    }

});