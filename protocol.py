# requests
REQ_NICKNAME = 'a'          #REQchr:nickname(str)+term
REQ_JOIN_EXIST_SESS = 'b'   #REQchr:sessName(str)+term
REQ_JOIN_NEW_SESS = 'c'     #REQchr:sessName(str)|maxPlayerNr(int)+term
REQ_PUT_NR = 'd'            #REQchr:xyz(int)+term

REQ_DICT = {
    REQ_NICKNAME: 'Client wants to connect with nickname'
    REQ_JOIN_EXIST_SESS: 'Client wants to join session'
    REQ_JOIN_NEW_SESS: 'Client wants to create new session'
    REQ_PUT_NR: 'Client wants to put number to sudoku table'
    }


# replies
REP_CURRENT_SESSIONS = '0'  #REPnr:[sessName|currentPlayerNr|maxPlayerNr, ...]+term
REP_CURRENT_PLAYERS = '1'   #REPnr:[nickname|score, ...]+term
REP_TABLE_UPDATE = '2'      #REPnr:sudokuTable(81 int)+term
REP_TABLE_SUCCESS = '3'     #REPnr:sudokuTable(81 int)+term
REP_TABLE_FULL = '4'        #REPnr:sudokuTable(81 int)+term
REP_TABLE_WRONG = '5'       #REPnr:sudokuTable(81 int)+term
REP_GAME_OVER = '6'         #REPnr:sudokuTable(81 int)+term

REP_NOT_OK = '9'            #REPnr:ErrorMsg+term

REP_DICT = {
    REP_CURRENT_SESSIONS: 'Sessions available on server'
    REP_CURRENT_PLAYERS: 'Players in session'
    REP_TABLE_UPDATE: 'Sudoku table update'
    REP_TABLE_SUCCESS: 'Sudoku table update - Correct number'
    REP_TABLE_FULL: 'Sudoku table update - Space occupied'
    REP_TABLE_WRONG: 'Sudoku table update - Incorrect number'
    REP_GAME_OVER: 'Game over - final scores'

    REP_NOT_OK: 'Try again'
    }

HEADER_SEP = ':'
FIELD_SEP = '|'
MSG_TERMCHR = '#'


