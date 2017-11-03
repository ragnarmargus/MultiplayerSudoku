import numpy as np
import random

def check_sudoku(sud):
	row = np.zeros(10, dtype=np.int)
	col = np.zeros(10, dtype=np.int)
	box = np.zeros(10, dtype=np.int)
	for i in range(9):
		for j in range(9):
			row[sud[i,j]] += 1
			col[sud[j,i]] += 1
			x = j%3 + (i%3*3)
			y = j//3 + (i//3*3)
			#print([x,y])
			box[sud[x,y]] += 1
		if np.max(row[1:])>1 or np.max(col[1:])>1 or np.max(box[1:])>1:
			return False
		else:
			row = np.zeros(10, dtype=np.int)
			col = np.zeros(10, dtype=np.int)
			box = np.zeros(10, dtype=np.int)
	return True

def solve_sudoku(sud,mul = False,sol=False):
	tmp = sud.copy()
	for i in range(9):
		for j in range(9):
			if sud[i,j]==0:
				for k in range(9):
					tmp[i,j]=k+1
					if check_sudoku(tmp):
						tmp,mul,sol = solve_sudoku(tmp,mul,sol)
						print(tmp)
						if np.min(tmp)>0:
							if mul:
								return sud, False, True
							return tmp, mul, True
				return sud, mul, sol
	if check_sudoku(tmp):
		return sud, mul, True
def make_sudoku2():
	sud = np.zeros((9,9), dtype=np.int)
	mul = False
	while(not mul):
		while True:
			tmp = sud.copy()
			tmp[int(random.random()*9),int(random.random()*9)] = int(random.random()*9)
			print(tmp)
			if check_sudoku(tmp):
				break
		
		_, mul, sol = solve_sudoku(tmp,True)
		if (sol):
			sud=tmp.copy()
	return sud

def make_sudoku():
	sud = np.zeros((9,9), dtype=np.int)
	a = np.array(range(9))+1
	np.random.shuffle(a)
	print(a)

	return sud

print(make_sudoku())
#sol, _,_ = solve_sudoku(make_sudoku(), False)
#print(solve_sudoku(sol, True))
#print(solve_sudoku(make_sudoku()))
#print(solve_sudoku(make_sudoku(), True))
