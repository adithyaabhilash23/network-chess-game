import socket
import threading
import json
import sys

HOST = '127.0.0.1'
PORT = 65432

INITIAL_BOARD = [
    ['r','n','b','q','k','b','n','r'],
    ['p','p','p','p','p','p','p','p'],
    ['.','.','.','.','.','.','.','.'],
    ['.','.','.','.','.','.','.','.'],
    ['.','.','.','.','.','.','.','.'],
    ['.','.','.','.','.','.','.','.'],
    ['P','P','P','P','P','P','P','P'],
    ['R','N','B','Q','K','B','N','R'],
]

def copy_board(board):
    return [row[:] for row in board]

def is_white(piece):
    return piece.isupper() and piece != '.'

def is_black(piece):
    return piece.islower() and piece != '.'

def is_enemy(piece, white_turn):
    return is_black(piece) if white_turn else is_white(piece)

def is_friendly(piece, white_turn):
    return is_white(piece) if white_turn else is_black(piece)

def in_bounds(r, c):
    return 0 <= r < 8 and 0 <= c < 8

def parse_square(s):
    s = s.strip().lower()
    if len(s) != 2 or s[0] not in 'abcdefgh' or s[1] not in '12345678':
        return None
    col = ord(s[0]) - ord('a')
    row = 8 - int(s[1])
    return (row, col)

def pawn_moves(board, r, c, white_turn):
    moves = []
    direction = -1 if white_turn else 1
    start_row = 6 if white_turn else 1
    nr = r + direction
    if in_bounds(nr, c) and board[nr][c] == '.':
        moves.append((nr, c))
        if r == start_row:
            nr2 = r + 2 * direction
            if board[nr2][c] == '.':
                moves.append((nr2, c))
    for dc in [-1, 1]:
        nr, nc = r + direction, c + dc
        if in_bounds(nr, nc) and is_enemy(board[nr][nc], white_turn):
            moves.append((nr, nc))
    return moves

def rook_moves(board, r, c, white_turn):
    moves = []
    for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
        nr, nc = r+dr, c+dc
        while in_bounds(nr, nc):
            if board[nr][nc] == '.':
                moves.append((nr, nc))
            elif is_enemy(board[nr][nc], white_turn):
                moves.append((nr, nc)); break
            else:
                break
            nr += dr; nc += dc
    return moves

def bishop_moves(board, r, c, white_turn):
    moves = []
    for dr, dc in [(-1,-1),(-1,1),(1,-1),(1,1)]:
        nr, nc = r+dr, c+dc
        while in_bounds(nr, nc):
            if board[nr][nc] == '.':
                moves.append((nr, nc))
            elif is_enemy(board[nr][nc], white_turn):
                moves.append((nr, nc)); break
            else:
                break
            nr += dr; nc += dc
    return moves

def knight_moves(board, r, c, white_turn):
    moves = []
    for dr, dc in [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]:
        nr, nc = r+dr, c+dc
        if in_bounds(nr, nc) and not is_friendly(board[nr][nc], white_turn):
            moves.append((nr, nc))
    return moves

def queen_moves(board, r, c, white_turn):
    return rook_moves(board, r, c, white_turn) + bishop_moves(board, r, c, white_turn)

def king_moves(board, r, c, white_turn):
    moves = []
    for dr in [-1,0,1]:
        for dc in [-1,0,1]:
            if dr == 0 and dc == 0:
                continue
            nr, nc = r+dr, c+dc
            if in_bounds(nr, nc) and not is_friendly(board[nr][nc], white_turn):
                moves.append((nr, nc))
    return moves

def get_piece_moves(board, r, c, white_turn):
    piece = board[r][c].upper()
    if piece == 'P': return pawn_moves(board, r, c, white_turn)
    if piece == 'R': return rook_moves(board, r, c, white_turn)
    if piece == 'B': return bishop_moves(board, r, c, white_turn)
    if piece == 'N': return knight_moves(board, r, c, white_turn)
    if piece == 'Q': return queen_moves(board, r, c, white_turn)
    if piece == 'K': return king_moves(board, r, c, white_turn)
    return []

def find_king(board, white_turn):
    king = 'K' if white_turn else 'k'
    for r in range(8):
        for c in range(8):
            if board[r][c] == king:
                return (r, c)
    return None

def is_in_check(board, white_turn):
    kr, kc = find_king(board, white_turn)
    for r in range(8):
        for c in range(8):
            piece = board[r][c]
            if piece == '.' or is_friendly(piece, white_turn):
                continue
            if (kr, kc) in get_piece_moves(board, r, c, not white_turn):
                return True
    return False

def apply_move(board, fr, fc, tr, tc, white_turn):
    new_board = copy_board(board)
    piece = new_board[fr][fc]
    new_board[tr][tc] = piece
    new_board[fr][fc] = '.'
    if piece == 'P' and tr == 0:
        new_board[tr][tc] = 'Q'
    if piece == 'p' and tr == 7:
        new_board[tr][tc] = 'q'
    return new_board

def get_legal_moves(board, r, c, white_turn):
    pseudo = get_piece_moves(board, r, c, white_turn)
    legal = []
    for tr, tc in pseudo:
        new_board = apply_move(board, r, c, tr, tc, white_turn)
        if not is_in_check(new_board, white_turn):
            legal.append((tr, tc))
    return legal

def has_any_legal_move(board, white_turn):
    for r in range(8):
        for c in range(8):
            piece = board[r][c]
            if piece == '.' or not is_friendly(piece, white_turn):
                continue
            if get_legal_moves(board, r, c, white_turn):
                return True
    return False

def board_to_list(board):
    return [row[:] for row in board]

class ChessGame:
    def __init__(self):
        self.board = copy_board(INITIAL_BOARD)
        self.white_turn = True
        self.game_over = False
        self.result = None
        self.lock = threading.Lock()

    def try_move(self, move_str, is_white_player):
        with self.lock:
            if self.game_over:
                return False, 'Game is already over.', None
            if is_white_player != self.white_turn:
                return False, 'It is not your turn.', None
            move_str = move_str.strip().replace(' ', '')
            if len(move_str) != 4:
                return False, 'Invalid format. Use e.g. e2e4', None
            from_sq = parse_square(move_str[:2])
            to_sq   = parse_square(move_str[2:])
            if from_sq is None or to_sq is None:
                return False, 'Invalid square.', None
            fr, fc = from_sq
            tr, tc = to_sq
            piece = self.board[fr][fc]
            if piece == '.':
                return False, 'No piece on that square.', None
            if is_white_player and not is_white(piece):
                return False, 'That is not your piece.', None
            if not is_white_player and not is_black(piece):
                return False, 'That is not your piece.', None
            legal = get_legal_moves(self.board, fr, fc, self.white_turn)
            if (tr, tc) not in legal:
                return False, 'Illegal move.', None

            # Detect capture before applying move
            captured = self.board[tr][tc] if self.board[tr][tc] != '.' else None

            self.board = apply_move(self.board, fr, fc, tr, tc, self.white_turn)
            self.white_turn = not self.white_turn

            status = 'ok'
            if is_in_check(self.board, self.white_turn):
                if not has_any_legal_move(self.board, self.white_turn):
                    winner = 'White' if not self.white_turn else 'Black'
                    self.game_over = True
                    self.result = f'Checkmate! {winner} wins!'
                    status = 'checkmate'
                else:
                    status = 'check'
            elif not has_any_legal_move(self.board, self.white_turn):
                self.game_over = True
                self.result = 'Stalemate! Draw.'
                status = 'stalemate'

            return True, status, captured

clients = [None, None]
client_names = ['White', 'Black']
game = ChessGame()

def send_msg(sock, data):
    try:
        msg = json.dumps(data) + '\n'
        sock.sendall(msg.encode())
    except Exception:
        pass

def recv_msg(sock):
    buf = b''
    while True:
        chunk = sock.recv(1)
        if not chunk:
            return None
        if chunk == b'\n':
            break
        buf += chunk
    try:
        return json.loads(buf.decode())
    except Exception:
        return None

def broadcast(data, exclude=None):
    for sock in clients:
        if sock and sock != exclude:
            send_msg(sock, data)

def handle_client(sock, player_index):
    color = client_names[player_index]
    is_white_player = (player_index == 0)
    print(f'[SERVER] {color} player connected.')
    send_msg(sock, {'type': 'waiting', 'msg': f'You are {color}. Waiting for opponent...'})
    while clients[1 - player_index] is None:
        import time; time.sleep(0.2)
    send_msg(sock, {
        'type': 'start',
        'color': color,
        'board': board_to_list(game.board),
        'turn': 'White',
        'msg': f'Game started! You are {color}.'
    })
    try:
        while True:
            msg = recv_msg(sock)
            if msg is None:
                print(f'[SERVER] {color} disconnected.')
                broadcast({'type': 'disconnect', 'msg': f'{color} disconnected. Game over.'}, exclude=sock)
                break
            if msg.get('type') == 'move':
                move_str = msg.get('move', '')
                print(f'[SERVER] {color} attempts: {move_str}')
                ok, status, captured = game.try_move(move_str, is_white_player)
                if not ok:
                    send_msg(sock, {'type': 'error', 'msg': status})
                    continue
                turn_color = 'White' if game.white_turn else 'Black'
                cap_log = f' captured {captured}' if captured else ''
                if status in ('checkmate', 'stalemate'):
                    broadcast({
                        'type': 'gameover',
                        'board': board_to_list(game.board),
                        'move': move_str.upper(),
                        'by': color,
                        'msg': game.result,
                        'captured': captured
                    })
                    print(f'[SERVER] {game.result}')
                    break
                else:
                    broadcast({
                        'type': 'moved',
                        'board': board_to_list(game.board),
                        'move': move_str.upper(),
                        'by': color,
                        'turn': turn_color,
                        'check': (status == 'check'),
                        'captured': captured
                    })
                    print(f'[SERVER] {move_str.upper()} by {color}.{cap_log} Turn: {turn_color}' +
                          (' CHECK!' if status == 'check' else ''))
    except Exception as e:
        print(f'[SERVER] Error with {color}: {e}')
    finally:
        sock.close()
        clients[player_index] = None

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(2)
    print(f'[SERVER] Chess server started on {HOST}:{PORT}')
    print(f'[SERVER] Waiting for 2 players...')
    player_count = 0
    while player_count < 2:
        conn, addr = server.accept()
        clients[player_count] = conn
        t = threading.Thread(target=handle_client, args=(conn, player_count), daemon=True)
        t.start()
        player_count += 1
        print(f'[SERVER] Player {player_count} connected from {addr}')
    print('[SERVER] Both players connected. Game is live!')
    try:
        while True:
            import time; time.sleep(1)
    except KeyboardInterrupt:
        print('\n[SERVER] Shutting down.')
        server.close()

if __name__ == '__main__':
    main()