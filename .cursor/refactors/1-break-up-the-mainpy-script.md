# Break Up The Mainpy Script

## Working directory

`~/Desktop/receipt-ranger`

## Contents

The main entry file main.py is too long. This file needs to only handle the overall logic of the application. Most of the functions and their logic can be extracted into other files. We should have a more modular architecture where there are separate directories and files for certain things. This file is doing a lot and it shouldn't have to bear all of this responsibility. 

## Acceptance criteria

- Entry file main.py will be much shorter, and most of the functions will be moved into other files. 
