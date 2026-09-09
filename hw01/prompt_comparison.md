# Prompt Engineering Comparison

## Strategy 1 - Zero-shot Strategy

### Complete Prompt
"What are the most important metrics for measuring credit risk in a consumer loan portfolio?"

### First 150 Words of Claude's Response
"This is a solid conceptual question I can answer directly — no need to dig into your project files unless you want it tied to Wildcat Capital specifically. Here's a rundown of the metrics that actually matter for assessing credit risk in a consumer loan portfolio.
Delinquency and default metrics form the core. You'd track delinquency rates by bucket — 30, 60, 90+ days past due — since the migration between buckets tells you whether risk is building before it hits full default. Default rate itself (accounts charged off or in serious default over a period) is the lagging confirmation. Roll rate, the percentage of accounts that move from one delinquency bucket to a worse one each month, is especially useful because it's forward-looking rather than a snapshot.
Loss metrics translate delinquency into dollar terms. Net charge-off rate (charge-offs minus recoveries, divided by average loan balance) is the standard headline number lenders report."

### Evaluation
This strategy did a good job of providing a detailed and comprehensive explanation of the different metrics used to measure credit risk. However, the response was very high-level and used a lot of technical terms, such as loss given default, probability of default, and RAROC, without explaining them in simple terms. It felt like the response assumed the reader already had a strong understanding of consumer lending and credit risk. Because of this, the information was thorough, but it was not as easy to understand or immediately apply for someone who is less familiar with the field. Also, note the response did not reference any files in Cowork and instead relied entirely on its own general knowledge. Because of this, the information was thorough, but it was not as specific to Wildcat Capital or the data being analyzed.


## Strategy 2 - Role-assigned Strategy

### Complete Prompt
"You are a manager presenting to your newly hired summer intern, what are the most important metrics for measuring credit risk in a consumer loan portfolio?"

### First 150 Words of Claude's Response
"Alright, pull up a chair. Let's say you just handed me the loan tape for our consumer book and asked "how worried should I be?" Here's what I'd actually look at, in the order I'd look at it.
First, I'd check delinquencies — who's behind on payments, broken into buckets like 30, 60, and 90+ days past due. Think of it like a funnel: not everyone who's 30 days late ends up defaulting, but almost everyone who defaults passed through 30 days late first. So I watch the roll rate — what percentage of accounts slide from one bucket to the next each month. If roll rates are climbing, that's an early warning sign before it ever shows up in our losses.
Second, I'd look at actual losses — the net charge-off rate. This is the number that eventually shows up on the income statement: loans we've written off as uncollectible, net of whatever we recovered."

### Evaluation
This strategy did a good job of explaining the important credit risk metrics in a much more understandable and conversational way. By asking the AI to respond as a manager speaking to a newly hired summer intern, it explained technical concepts using simpler language and examples, such as comparing delinquency to a funnel. This made the response easier to follow without requiring as much prior knowledge of consumer lending. However, similar to the first strategy, the response relied on its own general knowledge and did not reference or use any of the provided Wildcat Capital files or data. While the response was more approachable and practical, it was still fairly general rather than being specifically applied to Wildcat Capital.


## Strategy 3 - Few-shot Strategy

### Complete Prompt
"Example of the format I want:  
Metric 1: Customer Retention Rate  
What it measures: The percentage of customers who continue using the company over a given period.  
Why it matters: It helps a company understand customer loyalty and identify potential problems with customer satisfaction.

answer this question: What are the most important metrics for measuring credit risk in a consumer loan portfolio?"

### First 150 Words of Claude's Response
"Metric 1: Debt-to-Income Ratio (DTI)  
What it measures: The share of a borrower's gross monthly income that goes toward debt payments, including the loan being evaluated.  
Why it matters: A high DTI signals limited capacity to absorb a new payment obligation, making the borrower more likely to default if income drops or expenses rise.  
Metric 2: FICO / Credit Score  
What it measures: A borrower's creditworthiness based on payment history, credit utilization, length of credit history, and other bureau data.  
Why it matters: It's one of the strongest predictors of future default and lets a lender quickly segment applicants into risk tiers for pricing and approval decisions.  
Metric 3: Loan-to-Value Ratio (LTV)  
What it measures: The loan amount as a percentage of the value of the asset securing it (e.g., a car or home).  
Why it matters: A high LTV means less collateral cushion, so losses in the event of default are larger; it also correlates with borrower equity and commitment to the asset."

### Evaluation
This strategy did a good job of organizing the response into a clear and consistent format. By providing an example beforehand, Claude followed the same structure for every metric by explaining what it measures and why it matters. This made the information easy to read and quickly understand, especially compared to the first strategy, which gave a more technical response in paragraph form. However, some of the explanations still included technical terms that someone unfamiliar with credit risk may not fully understand. Like the other strategies, the response also relied on its own general knowledge rather than using or referencing the provided Wildcat Capital files and data.


## Conclusion

Overall, all three strategies provided useful information about credit risk, but the way the information was presented differed significantly. The first strategy gave a detailed response but was very technical and seemed to require prior knowledge of credit risk to fully understand it. The role-based strategy made the information easier to understand by explaining the metrics in a more conversational and practical way, while the few-shot strategy provided the clearest and most organized response. For a BI analyst, I think the few-shot strategy produced the most useful output because its consistent structure made it easy to identify each metric, understand what it measures, and see why it matters for business decisions.


## Fact-Check

### Exact Claim from Claude
> "Metric 1: Debt-to-Income Ratio (DTI)  
What it measures: The share of a borrower's gross monthly income that goes toward debt payments, including the loan being evaluated.  
Why it matters: A high DTI signals limited capacity to absorb a new payment obligation, making the borrower more likely to default if income drops or expenses rise."

### Source
**Source:** Ivestopedia

**URL:** (https://www.investopedia.com/terms/d/dti.asp)

### What the Source Says
Investopedia explains that the debt-to-income (DTI) ratio compares a person's monthly debt payments to their gross monthly income. Lenders use DTI to evaluate a borrower's ability to make loan payments and repay their debt. A lower DTI is generally viewed more favorably because it indicates that less of the borrower's income is already being used to pay existing debts.

### Comparison and Conclusion
Claude's claim agrees with the information provided by Investopedia. Both explain that DTI measures how much of a person's income goes toward debt payments and that a higher DTI can indicate greater difficulty taking on and repaying additional debt. Since Claude's explanation closely matches the information from an outside financial source, I would consider this type of claim from Claude to be reliable.
