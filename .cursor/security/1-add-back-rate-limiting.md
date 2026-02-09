---
github_issue: 25
---
# Add back rate limiting

## Working directory

`~/Desktop/receipt-ranger`

## Contents

We disabled rate limiting to get the deploy to work. Now we need to add it back. Find a rate that works.

Previously, rate limiting was breaking our deploys. It was causing lots of errors. My previous rule had a block when 100 requests were exceeded in 10 seconds. The block would last for 10 seconds. When we had this enabled, we were getting continuous errors. So we need to figure out a better rate that we can use to allow the site to still work. 

## Acceptance criteria

- There will be a rate limit protection that works. It will block malicious traffic while still enabling the site to work. 
