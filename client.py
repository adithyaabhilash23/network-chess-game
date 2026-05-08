import socket
import threading
import json
import sys
import os
import time

HOST = '127.0.0.1'
PORT = 65432

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

RESET   = '\033[0m'
BOLD    = '\033[1m'
WHITE_P = '\033[97m'
BLACK_P = '\033[33m'
GREEN   = '\033[92m'
RED     = '\033[91m'
CYAN    = '\033[96m'
DIM     = '\033[2m'

PIECE_UNICODE = {
    'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
    'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟',
}

def piece_display(p):
    sym = PIECE_UNICODE.get(p, ' ')
    if p.isupper() and p != '.':
        return WHITE_P + BOLD + sym + RESET
    elif p.islower():
        return BLACK_P + BOLD + sym + RESET
    else:
        return ' '

def render_board(board, my_color, captured_by_white, captured_by_black):
    lines = []
    flip = (my_color == 'Black')
    file_labels = ['a','b','c','d','e','f','g','h']
    if flip:
        file_labels = file_labels[::-1]
    header = '      ' + '    '.join(file_labels)

    # Build board rows first, then attach captured pieces on the right
    board_lines = []
    board_lines.append(CYAN + header + RESET)
    board_lines.append(CYAN + '   +----+----+----+----+----+----+----+----+' + RESET)
    row_range = range(7, -1, -1) if flip else range(8)
    for idx, r in enumerate(row_range):
        rank = str(8 - r)
        row_str = CYAN + ' ' + rank + ' ' + RESET
        col_range = range(7, -1, -1) if flip else range(8)
        for c in col_range:
            p = board[r][c]
            is_light = (r + c) % 2 == 0
            bg = '\033[48;5;235m' if is_light else '\033[48;5;239m'
            piece = piece_display(p)
            if p == '.':
                row_str += CYAN + '|' + RESET + bg + '    ' + RESET
            else:
                row_str += CYAN + '|' + RESET + bg + ' ' + piece + '  ' + RESET
        row_str += CYAN + '| ' + rank + RESET
        board_lines.append(row_str)
        board_lines.append(CYAN + '   +----+----+----+----+----+----+----+----+' + RESET)
    board_lines.append(CYAN + header + RESET)

    # Build captured pieces sidebar
    # captured_by_white = pieces white has captured (black pieces)
    # captured_by_black = pieces black has captured (white pieces)
    side = []
    side.append(f'  {WHITE_P}{BOLD}    Captured by White:{RESET}')
    if captured_by_white:
        row = '   '
        for p in captured_by_white:
            row += BLACK_P + BOLD + PIECE_UNICODE.get(p, p) + RESET + ' '
        side.append(row)
    else:
        side.append(f'   {DIM}none{RESET}')
    side.append('')
    side.append(f'  {BLACK_P}{BOLD}  Captured by Black:{RESET}')
    if captured_by_black:
        row = '   '
        for p in captured_by_black:
            row += WHITE_P + BOLD + PIECE_UNICODE.get(p, p) + RESET + ' '
        side.append(row)
    else:
        side.append(f'   {DIM}none{RESET}')

    # Pad side to same length as board_lines
    while len(side) < len(board_lines):
        side.append('')

    # Merge board and sidebar line by line
    for i, bline in enumerate(board_lines):
        sline = side[i] if i < len(side) else ''
        lines.append(bline + '    ' + sline)

    return '\n'.join(lines)

def print_status(my_color, turn, last_move=None, check=False, error=None, captured_msg=None):
    color_str = (WHITE_P + BOLD + 'White' + RESET) if my_color == 'White' else (BLACK_P + BOLD + 'Black' + RESET)
    turn_str  = (WHITE_P + BOLD + 'White' + RESET) if turn == 'White' else (BLACK_P + BOLD + 'Black' + RESET)
    print()
    print(f'   You are: {color_str}      Current turn: {turn_str}')
    if last_move:
        print(f'   Last move: {BOLD}{last_move}{RESET}')
    if captured_msg:
        print(f'   {RED}{BOLD}capture!{RESET} {captured_msg}')
    if check:
        print(f'   {RED}{BOLD}*** CHECK! ***{RESET}')
    if error:
        print(f'   {RED}Invalid: {error}{RESET}')
    print()

state = {
    'board': None,
    'my_color': None,
    'turn': None,
    'last_move': None,
    'check': False,
    'game_over': False,
    'game_over_msg': None,
    'waiting': True,
    'need_redraw': False,
    'error_msg': None,
    'captured_by_white': [],   # black pieces white has taken
    'captured_by_black': [],   # white pieces black has taken
    'captured_msg': None,
}

input_queue = []
input_lock  = threading.Lock()

def input_thread_fn():
    while not state['game_over']:
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            state['game_over'] = True
            break
        if line is not None:
            with input_lock:
                input_queue.append(line.strip())

def recv_loop(sock):
    buf = b''
    while True:
        try:
            chunk = sock.recv(1)
            if not chunk:
                state['game_over'] = True
                state['game_over_msg'] = 'Server disconnected.'
                state['need_redraw'] = True
                break
            if chunk == b'\n':
                try:
                    msg = json.loads(buf.decode())
                    handle_server_msg(msg)
                except Exception:
                    pass
                buf = b''
            else:
                buf += chunk
        except Exception:
            break

def handle_server_msg(msg):
    t = msg.get('type')
    if t == 'waiting':
        print(f'\n{DIM}  {msg["msg"]}{RESET}')
    elif t == 'start':
        state['my_color']    = msg['color']
        state['board']       = msg['board']
        state['turn']        = msg['turn']
        state['waiting']     = False
        state['need_redraw'] = True
    elif t == 'moved':
        state['board']       = msg['board']
        state['turn']        = msg['turn']
        state['last_move']   = msg['move'] + f' by {msg["by"]}'
        state['check']       = msg.get('check', False)
        state['error_msg']   = None
        state['captured_msg'] = None
        # Handle capture notification
        captured = msg.get('captured')
        if captured:
            by = msg['by']
            piece_name = {
                'p':'Pawn','r':'Rook','n':'Knight','b':'Bishop','q':'Queen','k':'King',
                'P':'Pawn','R':'Rook','N':'Knight','B':'Bishop','Q':'Queen','K':'King',
            }.get(captured, captured)
            owner = 'White' if captured.isupper() else 'Black'
            state['captured_msg'] = f'{by} captured {owner}\'s {piece_name}!'
            if by == 'White':
                state['captured_by_white'].append(captured.lower())
            else:
                state['captured_by_black'].append(captured.upper())
        state['need_redraw'] = True
    elif t == 'error':
        state['error_msg']   = msg['msg']
        state['need_redraw'] = True
    elif t == 'gameover':
        state['board']         = msg['board']
        state['last_move']     = msg['move'] + f' by {msg["by"]}'
        state['game_over']     = True
        state['game_over_msg'] = msg['msg']
        captured = msg.get('captured')
        if captured:
            if msg['by'] == 'White':
                state['captured_by_white'].append(captured.lower())
            else:
                state['captured_by_black'].append(captured.upper())
        state['need_redraw']   = True
    elif t == 'disconnect':
        state['game_over']     = True
        state['game_over_msg'] = msg['msg']
        state['need_redraw']   = True

def send_msg(sock, data):
    msg = json.dumps(data) + '\n'
    sock.sendall(msg.encode())

def main():
    clear()
    print(f'{CYAN}{BOLD}')
    print('   +================================+')
    print('   |    CHESS  --  NETWORK GAME     |')
    print('   +================================+')
    print(RESET)
    print(f'   Connecting to {HOST}:{PORT} ...')
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((HOST, PORT))
    except ConnectionRefusedError:
        print(f'\n{RED}   Could not connect. Is the server running?{RESET}')
        sys.exit(1)
    print(f'{GREEN}   Connected!{RESET}')

    t_recv = threading.Thread(target=recv_loop, args=(sock,), daemon=True)
    t_recv.start()

    t_input = threading.Thread(target=input_thread_fn, daemon=True)
    t_input.start()

    print(f'   Waiting for another player to join...\n')
    while state['waiting'] and not state['game_over']:
        time.sleep(0.2)

    if state['game_over']:
        print(state.get('game_over_msg', ''))
        return

    while not state['game_over']:
        if state['need_redraw']:
            state['need_redraw'] = False
            clear()
            print(f'{CYAN}{BOLD}   CHESS  --  NETWORK GAME{RESET}\n')
            print(render_board(state['board'], state['my_color'],
                               state['captured_by_white'], state['captured_by_black']))
            print_status(state['my_color'], state['turn'],
                         state['last_move'], state['check'],
                         state['error_msg'], state['captured_msg'])
            state['error_msg']   = None
            state['captured_msg'] = None
            my_turn = (state['turn'] == state['my_color'])
            if my_turn:
                print(f'   {GREEN}{BOLD}Your move (e.g. e2e4): {RESET}', end='', flush=True)
            else:
                print(f'   {DIM}Waiting for opponent...{RESET}', flush=True)

        if state['game_over']:
            break

        my_turn = (state['turn'] == state['my_color'])

        with input_lock:
            pending = input_queue.copy()
            input_queue.clear()

        for move in pending:
            if move.lower() in ('quit', 'exit', 'q'):
                print('\n   Bye!')
                sock.close()
                return
            if not my_turn:
                continue
            if len(move.replace(' ', '')) == 4:
                send_msg(sock, {'type': 'move', 'move': move})
            else:
                state['error_msg'] = 'Enter a move like e2e4'
                state['need_redraw'] = True

        time.sleep(0.05)

    clear()
    print(f'{CYAN}{BOLD}   CHESS  --  NETWORK GAME{RESET}\n')
    if state['board']:
        print(render_board(state['board'], state['my_color'],
                           state['captured_by_white'], state['captured_by_black']))
    print()
    print(f'   {RED}{BOLD}{"=" * 38}{RESET}')
    print(f'   {BOLD}   {state["game_over_msg"]}{RESET}')
    print(f'   {RED}{BOLD}{"=" * 38}{RESET}\n')
    input('   Press Enter to exit...')
    sock.close()

if __name__ == '__main__':
    main()