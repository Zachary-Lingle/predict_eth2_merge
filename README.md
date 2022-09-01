# predict_eth2_merge

## Declaration
The inspiration and part of the source code for the project comes from [predict_ttd](https://github.com/taxmeifyoucan/predict_ttd)

## How to use

### Step 1: Edit .env file
Infura will be **automatically** selected as the running provider of WEB3 in the project. Of course. Local Node is much **faster** than Infura.
```
#INFURA
INFURA_URL=''

#LOCAL
LOCAL_URL='http://127.0.0.1:8545'
```

### Step 2: Run data.py
There are two functions in data.py, get_points and update.
```
    get_points() # For first running
    update() # For following
```
    
### Step 3: Run Analysis.py
```
    analyze() # main function to calculate the Merge time (root).
```