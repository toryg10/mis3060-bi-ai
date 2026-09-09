# Business Context Exploration

## Question 1

### Exact Prompt
Is there a relationship between annual income and credit score, and what might this indicate about a consumer’s credit risk?

### Follow-Up Question
Is DTI a better predictor?

### Summary of Claude's Responses (from initial prompt & follow-up question)
Income and credit score are not related; earning more does not mean having a better credit score (correlation of -0.04), which makes sense since income measures capacity to pay while credit score reflects actual repayment behavior over time. Credit score is the strongest predictor of default: borrowers with poor scores default about 6 times more often than those with excellent scores. Debt-to-income ratio has only a weak effect on default, far less than credit score. Credit score matters most for spotting risky borrowers, income alone isn't useful for that, and debt-to-income is only a minor factor.

## Question 2

### Exact Prompt
What would a portfolio committee typically want to see in a quarterly review, for a lender with Wildcat's specific loan-purpose mix (Auto, Personal, Home Improvement, Education, Business)?

### Summary of Claude's Response (from initial prompt)
A quarterly portfolio committee mainly wants to know if loan risk is getting better or worse, and where. They'll want to see default and delinquency rates broken out by loan purpose (Auto, Personal, Home Improvement, Education, Business), not just one overall number, since problems can hide inside a single category. They also want to track newer loans separately from older ones, since new loans haven't had time to default yet and can make things look safer than they are. They'll check whether risk is concentrated too heavily in one loan type or region. Finally, they want early-warning signs, like loans slipping from on-time into late, so problems can be caught before they turn into full defaults.

### Follow-Up Question
Is there any concern in each of the loan types in a specific region that has high default rates?

## Question 3

### Exact Prompt
What is the difference between delinquency and default, and how does that trace to Wildcat's four status categories?

### Summary of Claude's Response (from initial prompt)
Delinquency means a borrower missed a payment but can still catch up and recover. Default means the loan is considered a lost cause and gets written off. So delinquency is a warning sign, while default is the actual failure. In Wildcat's four categories, Current and Paid Off are the healthy outcomes, Delinquent is the warning stage, and Default is the final bad outcome. Tracking how many Delinquent loans recover versus slide into Default is more useful than just looking at each status on its own.

### Follow-Up Question
Which of the 5 loan purposes is the worst to best in terms of default rate?
