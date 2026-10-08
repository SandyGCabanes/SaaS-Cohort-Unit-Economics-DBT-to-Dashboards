# Decision log 

Here is the full, detailed story of how we updated the synthetic data generator across seven versions. Every technical change was made to fix a specific flaw, and we verified each update against our testing script before moving forward.

**v1 to v2**
In version 1, monthly revenue was recalculated from scratch each month instead of compounding, which capped our Net Retention Rate, or NRR, below 100%. NRR measures how much revenue grows from existing customers over time. The generator was running a random monthly coin flip for upgrades that could never build on top of each other. We replaced that randomness with a fixed expansion curve that scales by customer channel. For example, referral customers expand faster than ad customers. This fix brought revenue retention into the 90% to 111% range, allowing middle cohorts to cross 100% in later months.

**v2 to v3**
Next, we cleaned up our math functions. We had two separate functions filling in missing data points between fixed checkpoints. One function built retention curves and the other built expansion curves. We merged them into a single shared function while keeping the downstream output calculations separate. We verified this by running a dataset of 33,065 rows across 4,109 unique customers. Both output files generated cleanly with zero changes to customer counts or cohort shapes.

**v3 to v4**
In version 4, we accounted for customer plan tiers when calculating Customer Acquisition Cost, or CAC. CAC is the money spent to win a new customer. Before this, landing a large Enterprise deal was priced as if it cost the same as a self-serve Basic signup. We made a calculated guess that higher tier plans cost a consistent multiple more to close, regardless of channel. We added cost multipliers of 1.0 for Basic, 3.0 for Pro, and 10.0 for Enterprise. Before this change, the ratio of Customer Lifetime Value, or CLV, to acquisition cost reached 708x for Enterprise deals. Moving from channel-level outputs to segment-level outputs expanded our customer cost table from 72 rows to 216 rows. We also updated the validation script to match this change.

**v4 to v4a**
We tried to lower the inflated acquisition ratios by manually tuning base costs. For example, we manually raised base costs for Ads from 150 to 550, Organic from 40 to 250, and Referral from 60 to 450. On paper, Enterprise Organic clv_cac ratios dropped from 70x down to 11.2x. However, when we ran the saas_generation script, actual Ad ratios dropped down to 1x and Organic dropped to 3x. Manually tweaking one number kept breaking another, creating an endless loop. We abandoned manual tuning and decided to work backward from a target ratio grid instead.

**v4a to v5**
To make that grid work, we built a solver to calculate the required Average Revenue Per User, or ARPU. The first attempt failed because it assumed every customer group lived a full 24 months. In reality, customer groups created late in the timeline get cut off early by the end of the panel. We rebuilt the solver to weight billing cycles by actual visible months. We also realized three deeper issues were pulling simulation numbers down. These were customer count rounding, lost expansion from early customer churn, and revenue contraction. The original math assumed an 18-month average lifespan and used a 2.45x guesswork multiplier. We rebuilt the solver a second time to account for a realistic 8-month average lifespan, needing only a 1.10x buffer to hit our target ratios.

**v5 to v6**
In version 6, we refined our adjustment buffers. Using a flat 1.10x buffer everywhere was under-correcting ad channels while over-correcting organic and referral channels. We gave ads an isolated 1.65x buffer and kept a 1.05x default buffer for other channels. We also added customer lifetime value, acquisition cost, and ratio metrics directly as calculated columns in the output files. We also cleaned up variable names to make the code easier to read.

**v6 to v7**
Finally, we secured our settings. All our hardcoded constants were sitting visible in the public script. We extracted every setting into a private configuration file and added it to our ignore file. The public script now will not run and throws an error if that private config file is missing. When we tested a clean folder without the private file, it halted immediately with zero output files created.

**v7 to v8**
In version 8, we deleted the channel calibration buffers entirely. The solver buffers in version 7 were creating a huge price gap, forcing Ads customers to pay 3.4x to 3.9x more than Organic or Referral customers on the exact same plan tier. Deleting the buffer mechanism allowed the solver to calculate baseline prices directly from target ratios, while channel retention, expansion, and acquisition costs were adjusted in the config file instead. As a result, the price gap between channels narrowed to a realistic 1.2x to 1.4x range.

**v8 to v9.1**
In version 9.1, we capped customer lifetime value tracking at 24 months and fixed errors in the solver math. Summing revenue up to 84 months was unfairly inflating lifetime value ratios against a one-time acquisition cost. We capped the window at 24 months, fixed month 0 retention at 100%, and changed monthly plan downgrades from exponential compounding to a flat risk multiplier. We also renamed output columns to specify the 24-month horizon and added a maturity flag so incomplete customer groups could be identified clearly.

**v9.1 to v9.2**
In version 9.2, we stopped solving for prices backward and switched to standardized list pricing. Calculating prices backward caused Organic customers to pay up to 34% less than Ads customers for the exact same tier. We set fixed list prices of $20 for Basic, $60 for Pro, and $600 for Enterprise, and removed target ratios from the setup file. Instead of driving prices, unit economic ratios became natural outputs of each channel's underlying retention, expansion, and acquisition costs.

**Validation**
Every version was tested against the `saas_validation.ipynb` script. The checks just evolved over time. Early on, we checked visual heatmaps by eye. By version 6, we used direct column checks. By version 7, we checked whether the script correctly refused to run without the private files. By version 9, we checked whether customer group ratios landed cleanly within expected ranges.
