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


def make_puzzle(board, best_move):
    san_move = board.san(best_move)
    side = "White" if board.turn == chess.WHITE else "Black"
    svg_board = chess.svg.board(
        board=board,
        size=420,
        flipped=(board.turn == chess.BLACK)
    )

    return {
        "fen": board.fen(),
        "answer": san_move,
        "side": side,
        "svg": svg_board
    }


def extract_puzzles(pgn_text):
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        return []

    board = game.board()
    puzzles = []

    fallback_puzzle = None
    fallback_score = -1

    for move in game.mainline_moves():
        info_before = engine.analyse(board, chess.engine.Limit(depth=8))
        eval_before = info_before["score"].white().score(mate_score=10000)

        board.push(move)

        info_after = engine.analyse(board, chess.engine.Limit(depth=8))
        eval_after = info_after["score"].white().score(mate_score=10000)

        if eval_before is None or eval_after is None:
            continue

        eval_diff = abs(eval_after - eval_before)

        board.pop()

        solution = engine.analyse(board, chess.engine.Limit(depth=10))
        best_move = solution["pv"][0]

        candidate = make_puzzle(board, best_move)

        if eval_diff > fallback_score:
            fallback_score = eval_diff
            fallback_puzzle = candidate

        analysis = engine.analyse(board, chess.engine.Limit(depth=10), multipv=2)
        if len(analysis) < 2:
            board.push(move)
            continue

        best_score = analysis[0]["score"].white().score(mate_score=10000)
        second_score = analysis[1]["score"].white().score(mate_score=10000)

        if best_score is None or second_score is None:
            board.push(move)
            continue

        if (
            eval_diff > 80
            and abs(best_score - second_score) >= 60
            and (board.is_capture(best_move) or board.gives_check(best_move))
        ):
            puzzles.append(candidate)

            if len(puzzles) >= 3:
                break

        board.push(move)

    if puzzles:
        return puzzles

    if fallback_puzzle:
        return [fallback_puzzle]

    return []


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
