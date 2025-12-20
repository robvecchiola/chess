from flask import Flask, render_template, request, jsonify
import chess
import chess.svg

app = Flask(__name__)

# Initialize a global board
board = chess.Board()

@app.route("/")
def home():
    return render_template("chess.html")

@app.route("/move", methods=["POST"])
def move():
    global board
    data = request.get_json()
    from_square = data.get("from")
    to_square = data.get("to")
    move_uci = from_square + to_square

    try:
        move = chess.Move.from_uci(move_uci)
        if move in board.legal_moves:
            board.push(move)
            turn = 'white' if board.turn == chess.WHITE else 'black'
            check = board.is_check()
            return jsonify({"status": "ok", "fen": board.fen(), "turn": turn, "check": check})
        else:
            return jsonify({"status": "illegal"})
    except:
        return jsonify({"status": "error"})

@app.route("/reset", methods=["POST"])
def reset():
    global board
    board.reset()
    return jsonify({"status": "ok"})