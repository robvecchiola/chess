$(document).ready(function() {
    var board = Chessboard('board', {
        draggable: true,
        position: 'start',
        pieceTheme: '/static/images/chesspieces/wikipedia/{piece}.png',
        onDrop: function(source, target, piece, newPos, oldPos, orientation) {
            $.ajax({
                url: "/move",
                type: "POST",
                contentType: "application/json",
                data: JSON.stringify({from: source, to: target}),
                success: function(response) {
                    if (response.status === "ok") {
                        board.position(response.fen);
                        updateStatus(response.turn, response.check);
                    } else {
                        board.position(oldPos);
                        alert("Illegal move!");
                    }
                }
            });
        }
    });

    // Reset button
    $("#reset-btn").click(function() {
        $.ajax({
            url: "/reset",
            type: "POST",
            success: function(response) {
                if (response.status === "ok") {
                    board.start();
                    updateStatus('white', false);
                }
            }
        });
    });

    // Function to update status div
    function updateStatus(turn, check) {
        let statusText = (turn === 'white') ? "White's turn" : "Black's turn";
        if (check) {
            statusText += " - Check!";
        }
        $("#game-status").text(statusText);
    }
});