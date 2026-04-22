from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import chess
import chess.pgn
import chess.engine
import chess.svg
import io
import os

app = Flask(__name__)
CORS(app)

STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "stockfish")
engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)


def extract_puzzles(pgn_text):
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        return []

    board = game.board()
    puzzles = []

    for move in game.mainline_moves():
        info_before = engine.analyse(board, chess.engine.Limit(depth=12))
        eval_before = info_before["score"].white().score(mate_score=10000)

        board.push(move)

        info_after = engine.analyse(board, chess.engine.Limit(depth=12))
        eval_after = info_after["score"].white().score(mate_score=10000)

        if eval_before is not None and eval_after is not None and abs(eval_after - eval_before) > 80:
            board.pop()

            solution = engine.analyse(board, chess.engine.Limit(depth=15))
            best_move = solution["pv"][0]

            analysis = engine.analyse(board, chess.engine.Limit(depth=15), multipv=2)
            if len(analysis) < 2:
                board.push(move)
                continue

            best_score = analysis[0]["score"].white().score(mate_score=10000)
            second_score = analysis[1]["score"].white().score(mate_score=10000)

            if best_score is None or second_score is None:
                board.push(move)
                continue

            if abs(best_score - second_score) < 80:
                board.push(move)
                continue

            if not (board.is_capture(best_move) or board.gives_check(best_move)):
                board.push(move)
                continue

            san_move = board.san(best_move)
            side = "White" if board.turn == chess.WHITE else "Black"

            svg_board = chess.svg.board(
                board=board,
                size=420,
                flipped=(board.turn == chess.BLACK)
            )

            puzzles.append({
                "fen": board.fen(),
                "answer": san_move,
                "side": side,
                "svg": svg_board
            })

            board.push(move)

    return puzzles[:5]


@app.route("/")
def home():
    return send_file("puzzle.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}
    pgn = data.get("pgn", "")
    puzzles = extract_puzzles(pgn)
    return jsonify(puzzles)


if __name__ == "__main__":
    app.run()
