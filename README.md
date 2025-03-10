# NFT Deep Appraisal

A consensus learning approach for evaluating the current value of NFTs. 

## Implementaton Summary
Our core implementation uses OpenRouter to distribute appraisal queries to models including Claude, Gemini, and Llama, each analyzing the NFT's sales history, rarity metrics, and market positioning. We consistently focus on prompt engineering and model verifiability, as all relevant data is fed from the Moralis API in real-time. 

## Consensus Approaches
We developed two consensus approaches: a baseline central aggregator that combines model responses and attaches a consensus upon each evaluation, and an advanced confidence-based system that challenges each model's reasoning consistency and assigns proportional weights based on Shapley value calculations, for which we applied a weighted formula of 70% price consistency and 30% explanation coherence. 


## TEEs and Insights from Project
This system runs inside Google's Confidential Space TEE with vTPM attestation, ensuring secure processing of potentially sensitive financial data. We implemented comprehensive testing protocols that demonstrate a decent improvement in accuracy compared to single-model approaches. Our implementation includes custom JSON parsing, error resilience mechanisms, and dynamic weight normalization to handle the variability of AI model responses. There were interestingly quite a few inconsistencies noted as different approaches performed better on different iterations (sometimes even single model ones), as this can largely be attributed to the inherent subjective nature of the NFT appraisal problem.
