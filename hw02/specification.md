# EDA Script Specification

## Purpose

Create one single Python script that performs a complete exploratory data analysis (EDA) of the `fact_transactions.csv` dataset. All requirements below must be completed by the same Python script in one execution.

## Requirements

The Python script should complete the following steps:

1. Load `02_Data/Raw/fact_transactions.csv` into a pandas DataFrame.

2. Print the shape of the dataset, including the number of rows and columns.

3. Print all column names and their data types.

4. Check every column for missing values and print the number of missing values for each column.

5. Print descriptive statistics for all numeric columns, including:
   - Count
   - Mean
   - Standard deviation
   - Minimum
   - 25th percentile
   - Median
   - 75th percentile
   - Maximum

6. Analyze `txn_type` by printing:
   - The count of each transaction type
   - The percentage of total transactions for each type
   
   Sort the results from most frequent to least frequent.

7. Print the number of unique clients, advisors, and securities referenced in the dataset.

8. Print the earliest and latest `txn_date` to show the date range of the dataset.

9. Check for duplicate rows based on `txn_id` and print the number of duplicates found.

10. Print the following statistics for the `amount` column:
    - Mean
    - Median
    - Skewness

11. Group the data by `txn_type`. For each transaction type, print:
    - Transaction count
    - Mean `amount`
    - Median `amount`
    
    Round the mean and median amounts to two decimal places. Sort the results from highest to lowest mean amount.

12. Calculate the correlation matrix for:
    - `shares`
    - `price`
    - `amount`
    
    Round the correlations to two decimal places and print the matrix. Also identify the three strongest correlations between different variables. Do not include a variable's correlation with itself.

13. For each `txn_type`, analyze the `shares` column and print:
    - Minimum value
    - Maximum value
    - Number of negative values

14. Check whether the dataset shape is exactly `(298772, 9)`. If the shape is different, print a warning.

15. Create and save three charts in the `hw02/charts/` folder:

    - Create a histogram of `amount` with clearly labeled vertical lines for the mean and median.
      - Save as `hw02/charts/hist_amount.png`

    - Create a horizontal box plot of `amount` grouped by `txn_type`.
      - Save as `hw02/charts/box_amount_by_type.png`

    - Create a scatter plot with `shares` on the x-axis and `amount` on the y-axis. Color the points based on `txn_type`.
      - Save as `hw02/charts/scatter_shares_amount.png`

16. Save a plain-text summary of the results from steps 2 through 13 to:
    `hw02/hw02_profile.txt`

17. Include a comment block at the top of the Python script that identifies:
    - The script
    - The dataset
    - The author
    - The generation date

## Final Instructions

This must be one Python script, not 17 separate scripts.

All 17 requirements must run together in the same file during one execution.

The script should be clear, organized, and easy to read.