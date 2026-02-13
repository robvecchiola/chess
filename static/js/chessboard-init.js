$(document).ready(function () {

    // =====================================================
    // 1. CONFIG + STATE
    // =====================================================

    const config = window.CHESS_CONFIG || {};
    const playerColor = "white"; // later this comes from auth/session

    let board;
    let pendingPromotion = null;
    let lastPosition = null;
    let currentTurn = config.turn || 'white';
    let isGameOver = false;
    let aiInFlight = false;
    let moveInFlight = false;
    let selectedSquare = null;
    let resizeTimeout;

    let initialPosition = config.fen || 'start';


    // =====================================================
    // 2. UTILITY HELPERS (Pure Logic)
    // =====================================================

    function capitalize(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }

    function canHumanMove() {
        return !isGameOver && !aiInFlight && !moveInFlight && currentTurn === playerColor;
    }

    function formatEvaluation(evalCp) {
        const abs = Math.abs(evalCp);

        if (abs < 30) return "Equal";

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

    function detectPromotion(source, target, piece) {
        if (piece[1] !== 'P') return { promotionNeeded: false };

        const isWhite = piece.startsWith('w');
        const finalRank = isWhite ? "8" : "1";

        if (!target.endsWith(finalRank)) return { promotionNeeded: false };

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

        if (position[target]) return { promotionNeeded: false };

        return { promotionNeeded: true };
    }

    window.detectPromotion = detectPromotion;


    // =====================================================
    // 3. UI RENDERING FUNCTIONS (DOM Updates Only)
    // =====================================================

    function updateErrorMessage(message) {
        $("#error-message").text(message);
    }

    function updateButtonVisibility(state) {
        const resetBtn = $("#reset-btn");
        const resignBtn = $("#resign-btn");
        const drawBtn = $("#offer-draw-btn");
        const claim50Btn = $("#claim-50-btn");
        const claimRepBtn = $("#claim-repetition-btn");

        if (state === 'game_active') {
            resetBtn.show();
            resignBtn.show();
            drawBtn.show();
        } else if (state === 'game_over') {
            resetBtn.show();
            resignBtn.hide();
            drawBtn.hide();
            claim50Btn.hide();
            claimRepBtn.hide();
        }
    }

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

    function updateStatus(state) {

        if (state.game_over) {
            let message = "Game over";

            switch (state.termination_reason) {
                case "resignation":
                    message = `${capitalize(state.winner)} wins — resignation`;
                    break;
                case "checkmate":
                    message = `${capitalize(state.winner)} wins — checkmate`;
                    break;
                case "draw_by_agreement":
                    message = "Draw — by agreement";
                    break;
                case "draw_threefold_repetition":
                    message = "Draw — threefold repetition";
                    break;
                case "draw_50_move_rule":
                    message = "Draw — 50-move rule";
                    break;
                case "stalemate":
                    message = "Draw — stalemate";
                    break;
                case "insufficient_material":
                    message = "Draw — insufficient material";
                    break;
            }

            $("#game-status").text(message);
            return;
        }

        let status;

        if (state.fifty_moves) {
            status = "50-move rule available";
        } else if (state.can_claim_repetition) {
            status = "Threefold repetition available";
        } else {
            status =
                state.turn === "white"
                    ? "White's turn"
                    : "Black's turn";
            if (state.check) status += " — Check!";
        }

        $("#game-status").text(status);
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
            el.text("Even")
              .removeClass("material-white material-black");
            return;
        }

        const pawns = Math.abs(material / 100).toFixed(1);

        if (material > 0) {
            el.text(`White +${pawns}`)
              .removeClass("material-black")
              .addClass("material-white");
        } else {
            el.text(`Black +${pawns}`)
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

    function updateSpecialMove(special_moves) {
        const whiteList = $("#special-white");
        const blackList = $("#special-black");

        if (!Array.isArray(special_moves)) return;

        whiteList.empty();
        blackList.empty();

        if (special_moves.length === 0) return;

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

            if (color === "white") whiteList.append(li);
            else if (color === "black") blackList.append(li);
            else whiteList.append(li);
        });
    }

    window.updateSpecialMove = updateSpecialMove;

    function showPromotionDialog(onPromotionSelected) {
        const dialog = document.getElementById("promotion-dialog");
        if (!dialog) {
            console.error("Promotion dialog element not found");
            return;
        }

        dialog.style.display = "block";

        // Set up promotion button handlers
        document.getElementById("promotion-q").onclick = () => {
            dialog.style.display = "none";
            onPromotionSelected("q");
        };
        document.getElementById("promotion-r").onclick = () => {
            dialog.style.display = "none";
            onPromotionSelected("r");
        };
        document.getElementById("promotion-b").onclick = () => {
            dialog.style.display = "none";
            onPromotionSelected("b");
        };
        document.getElementById("promotion-n").onclick = () => {
            dialog.style.display = "none";
            onPromotionSelected("n");
        };

        document.getElementById("cancel-promotion").onclick = () => {
            dialog.style.display = "none";
            moveInFlight = false;
            rollbackPosition();
            board.draggable = true;
        };
    }

    window.showPromotionDialog = showPromotionDialog;


    // =====================================================
    // 4. CORE STATE SYNC
    // =====================================================

    function updateFromState(state) {
        if (!state) return;

        pendingPromotion = null;
        updateErrorMessage("");

        // 🔑 CRITICAL: Reset flight flags to allow new moves
        // If a previous move left these flags true, it would block humanmove
        moveInFlight = false;
        aiInFlight = false;

        board.position(state.fen);
        currentTurn = state.turn;
        isGameOver = state.game_over;

        updateStatus(state);
        updateDrawButtons(state);
        updateCaptured(state.captured_pieces);
        updateMoveHistory(state.move_history);
        updateSpecialMove(state.special_moves);
        updateMaterialAdvantage(state.material);
        updatePositionEvaluation(state.evaluation);

        if (state.game_over) {
            board.draggable = false;
            updateButtonVisibility('game_over');
            loadAIRecord();
        } else {
            // Enable dragging when game is active
            board.draggable = true;
        }
    }


    // =====================================================
    // 5. SERVER / GAME ACTIONS
    // =====================================================

    function loadAIRecord() {
        $.get("/stats/ai-record", function (data) {
            $("#ai-wins").text(data.wins);
            $("#ai-losses").text(data.losses);
            $("#ai-draws").text(data.draws);
            $("#ai-winrate").text(`${data.win_rate}%`);
        });
    }

    function rollbackPosition() {
        if (pendingPromotion) {
            board.position(pendingPromotion.oldPos);
            pendingPromotion = null;
        } else if (lastPosition) {
            board.position(lastPosition);
        }
    }

    function sendMove(source, target, promotionPiece = null) {
        if (!canHumanMove()) return;

        moveInFlight = true;
        board.draggable = false;

        const payload = { from: source, to: target };
        if (promotionPiece) payload.promotion = promotionPiece;

        $.ajax({
            url: "/move",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify(payload),
            success: function (response) {
                moveInFlight = false;

                if (response.status === "ok" || response.status === "game_over") {
                    updateFromState(response);
                    maybeTriggerAiTurn(response);
                } else {
                    rollbackPosition();
                    updateErrorMessage(response.message || "Illegal move");
                    board.draggable = true;
                }
            },
            error: function (xhr) {
                moveInFlight = false;
                rollbackPosition();
                board.draggable = true;

                try {
                    const response = JSON.parse(xhr.responseText);
                    updateErrorMessage(response.message || "Server error");
                } catch (e) {
                    updateErrorMessage("Server error");
                }
            }
        });
    }

    window.sendMove = sendMove;

    function maybeTriggerAiTurn(state) {
        if (!state || state.game_over) return;
        if (state.turn !== "black") {
            board.draggable = true;
            return;
        }
        if (aiInFlight) return;

        aiInFlight = true;
        board.draggable = false;

        $.post("/ai-move", function (aiResponse) {
            aiInFlight = false;
            if (isGameOver) return;
            updateFromState(aiResponse);
        }).fail(function () {
            if (isGameOver) return;
            aiInFlight = false;
            board.draggable = true;
            updateErrorMessage("AI move failed.");
        });
    }


    // =====================================================
    // 6. BOARD SETUP
    // =====================================================

    board = Chessboard('board', {
        draggable: true,
        position: initialPosition,
        pieceTheme: '/static/images/chesspieces/wikipedia/{piece}.png',

        onDragStart: function (source, piece) {
            if (!canHumanMove()) return false;

            const pieceColor = piece.startsWith('w') ? 'white' : 'black';
            if (pieceColor !== currentTurn) return false;

            lastPosition = board.position();
        },

        onDrop: function (source, target, piece) {

            if (source === target) return 'snapback';

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

    // =====================================================
    // 7. EVENT BINDINGS
    // =====================================================

    function resizeBoardSafely() {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            if (board) board.resize();
        }, 250);
    }

    // 🔑 MOBILE: Handle square selection for touch/click on mobile
    function onSquareTap(square) {
        // If no square is selected, select this one as source
        if (!selectedSquare) {
            selectedSquare = square;
            // Highlight selected square for visual feedback
            const el = document.querySelector(`[data-square="${square}"]`);
            if (el) el.style.background = "rgba(37, 99, 235, 0.35)";
            return;
        }

        // Clear highlight
        document.querySelectorAll("[data-square]").forEach(el => {
            el.style.background = "";
        });

        // If same square tapped twice, deselect
        if (selectedSquare === square) {
            selectedSquare = null;
            return;
        }

        // Two different squares selected: attempt move
        const source = selectedSquare;
        const target = square;
        selectedSquare = null;

        // Check for promotion
        const fromPosition = board.position();
        const piece = fromPosition[source];

        if (piece) {
            const promotionCheck = detectPromotion(source, target, piece);

            if (promotionCheck.promotionNeeded) {
                moveInFlight = true;
                pendingPromotion = { source, target, oldPos: fromPosition };
                board.draggable = false;

                showPromotionDialog(function(selectedPiece) {
                    sendMove(pendingPromotion.source, pendingPromotion.target, selectedPiece);
                });
                return;
            }
        }

        sendMove(source, target);
    }

    window.addEventListener("resize", resizeBoardSafely);
    window.addEventListener("orientationchange", resizeBoardSafely);

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

    $("#reset-btn").click(function () {
        $.post("/reset", function(response) {
            if (response.status === "ok") {
                pendingPromotion = null;
                lastPosition = null;
                board.draggable = true;
                updateErrorMessage("");
                updateFromState(response);
                updateButtonVisibility('game_active');
            }
        });
    });

    $("#resign-btn").click(function () {
        $.ajax({
            url: "/resign",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({ color: playerColor }),
            success: function (response) {
                if (response.status === "ok") {
                    isGameOver = true;
                    updateFromState(response);
                    updateButtonVisibility('game_over');
                }
            }
        });
    });

    $("#offer-draw-btn").click(function () {
        $.ajax({
            url: "/draw-agreement",
            type: "POST",
            success: function (response) {
                if (response.status === "ok") {
                    updateFromState(response);
                }
            },
            error: function () {
                updateErrorMessage("Unable to offer draw.");
            }
        });
    });

    $("#claim-50-btn").click(function () {
        $.post("/claim-draw/50-move", function (response) {
            if (response.status === "ok") {
                updateFromState(response);
            } else {
                updateErrorMessage(response.message);
            }
        });
    });

    $("#claim-repetition-btn").click(function () {
        $.post("/claim-draw/repetition", function (response) {
            if (response.status === "ok") {
                updateFromState(response);
            } else {
                updateErrorMessage(response.message);
            }
        });
    });


    // =====================================================
    // 8. INITIAL BOOTSTRAP
    // =====================================================

    loadAIRecord();

    pendingPromotion = null;
    updateErrorMessage("");
    currentTurn = config.turn || currentTurn;
    isGameOver = config.game_over || false;

    updateDrawButtons(config);
    updateCaptured(config.captured_pieces);
    updateMoveHistory(config.move_history);
    updateSpecialMove(config.special_moves);
    updateMaterialAdvantage(config.material);
    updatePositionEvaluation(config.evaluation);
    updateStatus(config);

    const initialGameState = config.game_over ? 'game_over' : 'game_active';
    updateButtonVisibility(initialGameState);

    maybeTriggerAiTurn({turn: currentTurn, game_over: isGameOver});

});
