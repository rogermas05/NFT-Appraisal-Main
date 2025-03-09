"use client";

import { Info } from "lucide-react";
import { useEffect, useState } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { useNFTData } from "./NftDataContext";

// Available models for selection
const AVAILABLE_MODELS = [
  { id: "regression", name: "Centralized Aggregator" },
  { id: "confidence", name: "Confidence Adjusted Aggregator" },
  { id: "singular", name: "Singular Model Approach" },
] as const;

type ModelId = (typeof AVAILABLE_MODELS)[number]["id"];

export default function ModelComparison() {
  const [model1, setModel1] = useState<ModelId>("regression");
  const [model2, setModel2] = useState<ModelId>("confidence");
  const { nftData, isAppraisalLoading, selectedModels, setSelectedModels } =
    useNFTData();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Get model-specific data instead of just appraisalData
  const model1Data = nftData?.modelResults?.[model1];
  const model2Data = nftData?.modelResults?.[model2];

  // Get appraisal data for the centralized aggregator model
  const appraisalData = nftData?.appraisalData;

  // Calculate confidence percentage
  const confidencePercentage = appraisalData
    ? Math.round(appraisalData.total_confidence * 100)
    : 0;

  // Get standard deviation for model predictions
  const standardDeviation = appraisalData?.standard_deviation ?? 0;

  // Calculate accuracy percentage
  const accuracyPercentage =
    appraisalData && appraisalData.accuracy !== undefined
      ? Math.round(appraisalData.accuracy * 100)
      : 0;

  // Extract contract address and token ID from nftData
  const contractAddress =
    nftData?.contractAddress || nftData?.collectionAddress;
  const tokenId = nftData?.tokenId;

  // Updated helper functions to handle different API response formats
  const getEthereumPrice = (modelData: any, decimals: number = 2): string => {
    if (!modelData) return "-.--";

    // Direct ethereum price if available
    if (modelData.ethereum_price_usd !== undefined) {
      return modelData.ethereum_price_usd.toFixed(decimals);
    }

    // If the API only returns USD price, estimate ETH price
    // Assuming current ETH price of ~$2,500 for conversion
    if (modelData.price !== undefined) {
      const estimatedEthPrice = modelData.price / 2500;
      return estimatedEthPrice.toFixed(decimals);
    }

    return "-.--";
  };

  const getUsdPrice = (modelData: any, decimals: number = 2): string => {
    if (!modelData) return "-.--";

    // Direct USD price
    if (modelData.price !== undefined) {
      return modelData.price.toFixed(decimals);
    }

    return "-.--";
  };

  const getConfidencePercentage = (modelData: any) => {
    if (!modelData) return 0;

    // Different APIs use different field names for confidence
    if (modelData.total_confidence !== undefined) {
      return Math.round(modelData.total_confidence * 100);
    }

    if (modelData.final_confidence_score !== undefined) {
      return Math.round(modelData.final_confidence_score * 100);
    }

    // Add support for the single LLM model format
    if (modelData.confidence !== undefined) {
      return Math.round(modelData.confidence * 100);
    }

    return 0;
  };

  const getAccuracyPercentage = (modelData: any) => {
    if (!modelData || modelData.accuracy === undefined) return 0;
    
    // Handle the case where accuracy is a number between 0 and 1
    if (typeof modelData.accuracy === 'number') {
      // If accuracy is already between 0-100, return as is
      if (modelData.accuracy > 1) {
        return Math.round(modelData.accuracy);
      }
      // Otherwise, convert from 0-1 to 0-100
      return Math.round(modelData.accuracy * 100);
    }
    
    return 0;
  };

  const getModelExplanation = (modelData: any) => {
    if (!modelData) return "";

    // Different APIs use different field names for explanation text
    if (modelData.text) return modelData.text;
    if (modelData.explanation) return modelData.explanation;

    return "";
  };

  // Update this useEffect to sync model selections with context
  useEffect(() => {
    if (setSelectedModels) {
      setSelectedModels([model1, model2]);
    }
  }, [model1, model2, setSelectedModels]);

  // Add this near the top of your component
  useEffect(() => {
    if (appraisalData) {
      console.log("Appraisal data received:", appraisalData);
      console.log("Accuracy value:", appraisalData.accuracy);
    }
  }, [appraisalData]);

  // Log values to debug
  useEffect(() => {
    console.log("NFT Data:", nftData);
    console.log("Contract Address:", contractAddress);
    console.log("Token ID:", tokenId);
  }, [nftData, contractAddress, tokenId]);

  // Add this useEffect to detect the final_result event and flip the cards
  useEffect(() => {
    // Check if we have model data and if it contains the final_result event
    if (nftData?.modelResults) {
      const model1Data = nftData.modelResults[model1];
      const model2Data = nftData.modelResults[model2];
      
      // Check if model1 has final_result
      if (model1Data && 'final_result' in model1Data) {
        // Flip the card back to show the price appraisal
        setShowAnimation1(false);
      }
      
      // Check if model2 has final_result
      if (model2Data && 'final_result' in model2Data) {
        // Flip the card back to show the price appraisal
        setShowAnimation2(false);
      }
    }
  }, [nftData, model1, model2]);

  // Loading skeleton component
  const LoadingSkeleton = () => (
    <>
      {/* Price Prediction Skeleton */}
      <div className="rounded-lg bg-gray-800/50 p-6">
        <p className="mb-2 text-sm text-gray-400">Estimated Value</p>
        <div className="h-9 w-2/3 animate-pulse rounded-md bg-gray-700"></div>
      </div>

      {/* Confidence Score Skeleton */}
      <div className="rounded-lg bg-gray-800/50 p-6">
        <p className="mb-2 text-sm text-gray-400">Confidence Score</p>
        <div className="flex items-center gap-3">
          <div className="h-3 flex-1 animate-pulse rounded-full bg-gray-700"></div>
          <div className="h-5 w-10 animate-pulse rounded-md bg-gray-700"></div>
        </div>
      </div>

      {/* Accuracy Score Skeleton */}
      <div className="rounded-lg bg-gray-800/50 p-6">
        <p className="mb-2 text-sm text-gray-400">Accuracy Score</p>
        <div className="flex items-center gap-3">
          <div className="h-3 flex-1 animate-pulse rounded-full bg-gray-700"></div>
          <div className="h-5 w-10 animate-pulse rounded-md bg-gray-700"></div>
        </div>
      </div>

      {/* Explanation Text Skeleton - Make this more flexible */}
      <div className="rounded-lg bg-gray-800/50 p-6">
        <p className="mb-2 text-sm text-gray-400">Model Explanation</p>
        <div className="space-y-2">
          <div className="h-4 w-full animate-pulse rounded-md bg-gray-700"></div>
          <div className="h-4 w-5/6 animate-pulse rounded-md bg-gray-700"></div>
          <div className="h-4 w-4/6 animate-pulse rounded-md bg-gray-700"></div>
          <div className="h-4 w-3/4 animate-pulse rounded-md bg-gray-700"></div>
          <div className="h-4 w-2/3 animate-pulse rounded-md bg-gray-700"></div>
        </div>
      </div>
    </>
  );

  // Handle model selection with validation to prevent duplicate selections
  const handleModel1Change = (value: ModelId) => {
    // Check if the selected model is already chosen in the other window
    if (value === model2) {
      // Show error message
      setErrorMessage("Please choose a different model for comparison");
      // Clear the error message after 3 seconds
      setTimeout(() => setErrorMessage(null), 3000);
      return; // Don't update the state
    }
    setModel1(value);
  };

  const handleModel2Change = (value: ModelId) => {
    // Check if the selected model is already chosen in the other window
    if (value === model1) {
      // Show error message
      setErrorMessage("Please choose a different model for comparison");
      // Clear the error message after 3 seconds
      setTimeout(() => setErrorMessage(null), 3000);
      return; // Don't update the state
    }
    setModel2(value);
  };

  // Add tooltip component for reuse
  const InfoTooltip = ({
    text,
    children,
  }: {
    text: React.ReactNode;
    children?: React.ReactNode;
  }) => (
    <div className="group relative ml-1 inline-block">
      <Info
        size={16}
        className="cursor-help text-gray-400 hover:text-gray-300"
      />
      <div className="invisible absolute bottom-full left-1/2 z-10 mb-2 w-64 -translate-x-1/2 rounded-md bg-gray-700 p-2 text-xs text-gray-200 opacity-0 shadow-lg transition-all duration-200 group-hover:visible group-hover:opacity-100">
        {text}
        {children}
        <div className="absolute left-1/2 top-full -mt-1 -translate-x-1/2 border-4 border-transparent border-t-gray-700"></div>
      </div>
    </div>
  );

  // Create confidence tooltip content with weights standard deviation
  const confidenceTooltipContent = (modelId: ModelId, modelData: any) => {
    const baseText =
      "Confidence score represents how certain the model is about its prediction. Higher values indicate greater confidence in the estimated value.";

    if (modelId === "confidence" && modelData && modelData.weights_standard_deviation !== undefined) {
      return (
        <>
          {baseText}
          <div className="mt-2 border-t border-gray-600 pt-2">
            <span className="font-semibold">Weights Standard Deviation:</span>{" "}
            {modelData.weights_standard_deviation.toFixed(3)}
            <p className="mt-1">
              This value shows how much the weights between different language models vary. 
              Lower standard deviation indicates more balanced contribution from all models.
            </p>
          </div>
        </>
      );
    } else if (modelData && modelData.standard_deviation) {
      return (
        <>
          {baseText}
          <div className="mt-2 border-t border-gray-600 pt-2">
            <span className="font-semibold">Standard Deviation:</span>{" "}
            {modelData.standard_deviation.toFixed(2)}
            <p className="mt-1">
              This value shows how much the predictions from different models
              vary. Lower standard deviation indicates better agreement between
              models.
            </p>
          </div>
        </>
      );
    }

    return baseText;
  };

  // Update the LLMWeightsDisplay component to include tooltips with text similarity and price change
  const LLMWeightsDisplay = ({ modelData }: { modelData: any }) => {
    if (!modelData || !modelData.models) return null;
    
    return (
      <div className="rounded-lg bg-gray-800/50 p-6">
        <div className="mb-2 flex items-center text-sm text-gray-400">
          Model Weights
          <InfoTooltip text="Shows how different language models contribute to the final prediction. Higher weights indicate greater influence on the result." />
        </div>
        <div className="space-y-3 mt-2">
          {Object.entries(modelData.models).map(([modelName, data]: [string, any]) => (
            <div key={modelName} className="space-y-1">
              <div className="flex justify-between text-xs">
                <div className="flex items-center gap-1">
                  <span className="text-gray-300">{modelName.split('/').pop()}</span>
                  <InfoTooltip 
                    text={
                      <>
                        <div className="space-y-1">
                          <div><span className="font-semibold">Text Similarity:</span> {(data.text_similarity * 100).toFixed(1)}%</div>
                          <div><span className="font-semibold">Price Change:</span> {(data.price_change * 100).toFixed(1)}%</div>
                        </div>
                        <div className="mt-2 text-xs text-gray-400">
                          Text similarity measures how well the model's explanation aligns with others.
                          Price change shows how much the model adjusted its initial price estimate.
                        </div>
                      </>
                    } 
                  />
                </div>
                <span className="text-gray-400">{(data.weight * 100).toFixed(1)}%</span>
              </div>
              <div className="h-2 w-full rounded-full bg-gray-700">
                <div
                  className="h-full rounded-full bg-purple-500/70"
                  style={{ width: `${data.weight * 100}%` }}
                ></div>
              </div>
            </div>
          ))}
        </div>
        {modelData.weights_standard_deviation !== undefined && (
          <div className="mt-3 text-xs text-gray-400">
            <span className="font-semibold">Weight Deviation:</span> {modelData.weights_standard_deviation.toFixed(3)}
          </div>
        )}
      </div>
    );
  };

  // Update the accuracy tooltip to include the actual sale price information
  const accuracyTooltipContent = (modelData: any) => {
    const baseText = "Accuracy score measures how close the model's predictions have been to actual sale prices historically. Higher values indicate better predictive performance.";
    
    if (modelData && modelData.actual_value !== undefined) {
      return (
        <>
          {baseText}
          <div className="mt-2 border-t border-gray-600 pt-2">
            <span className="font-semibold">Actual Sale Price:</span> ${modelData.actual_value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
            <p className="mt-1">
              This is the verified price this NFT actually sold for in a recent transaction.
            </p>
          </div>
        </>
      );
    }
    
    return baseText;
  };

  // Update the LLMPredictionsDisplay component to match text styling with LLMWeightsDisplay
  const LLMPredictionsDisplay = ({ modelData }: { modelData: any }) => {
    if (!modelData || !modelData.models) return null;
    
    return (
      <div className="rounded-lg bg-gray-800/50 p-6">
        <div className="mb-2 flex items-center text-sm text-gray-400">
          Individual Model Predictions
          <InfoTooltip text="Shows the price predictions from each language model that contributed to the final aggregated price." />
        </div>
        <div className="space-y-3 mt-2">
          {Object.entries(modelData.models).map(([modelName, price]: [string, any]) => (
            <div key={modelName} className="flex justify-between items-center">
              <span className="text-xs text-gray-300">{modelName.split('/').pop()}</span>
              <span className="text-xs font-medium">${typeof price === 'number' ? price.toLocaleString() : price}</span>
            </div>
          ))}
          {modelData.standard_deviation !== undefined && (
            <div className="mt-3 pt-3 border-t border-gray-700 text-xs text-gray-400">
              <span className="font-semibold">Standard Deviation:</span> ${modelData.standard_deviation.toFixed(2)}
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      {/* Error message toast */}
      {errorMessage && (
        <div className="fixed right-4 top-4 z-50 rounded-md bg-red-500 px-4 py-2 text-white shadow-lg duration-300 animate-in fade-in slide-in-from-top-5">
          {errorMessage}
        </div>
      )}

      <div className="flex flex-1 gap-6">
        {/* Model 1 Output */}
        <div className="flex-1">
          <div className="flex h-full flex-col rounded-xl bg-gray-800/30 p-6">
            <div className="flex-1 space-y-6">
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-bold">Model Prediction</h2>
                  <Select value={model1} onValueChange={handleModel1Change}>
                    <SelectTrigger className="w-60 rounded-full bg-blue-500/20 px-3 py-1 text-sm text-blue-400">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-gray-200 text-gray-900">
                      {AVAILABLE_MODELS.map((model) => (
                        <SelectItem
                          key={model.id}
                          value={model.id}
                          className="hover:bg-gray-300 focus:bg-gray-300"
                        >
                          {model.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Content section */}
              {isAppraisalLoading ? (
                <LoadingSkeleton />
              ) : (
                <>
                  {/* Price Prediction */}
                  <div className="rounded-lg bg-gray-800/50 p-6">
                    <p className="mb-2 text-sm text-gray-400">
                      Estimated Value
                    </p>
                    <p className="text-3xl font-bold text-blue-400">
                      {model1Data
                        ? `${getEthereumPrice(model1Data)} ETH ($${getUsdPrice(model1Data)})`
                        : "-.-- ETH"}
                    </p>
                  </div>

                  {/* Confidence Score */}
                  <div className="rounded-lg bg-gray-800/50 p-6">
                    <div className="mb-2 flex items-center text-sm text-gray-400">
                      Confidence Score
                      <InfoTooltip
                        text={confidenceTooltipContent(model1, model1Data)}
                      />
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="h-3 flex-1 rounded-full bg-gray-700">
                        <div
                          className="h-full rounded-full bg-blue-500"
                          style={{
                            width: `${getConfidencePercentage(model1Data)}%`,
                          }}
                        ></div>
                      </div>
                      <span className="text-sm font-medium">
                        {getConfidencePercentage(model1Data)}%
                      </span>
                    </div>
                  </div>

                  {/* Accuracy Score */}
                  <div className="rounded-lg bg-gray-800/50 p-6">
                    <div className="mb-2 flex items-center text-sm text-gray-400">
                      Accuracy Score
                      <InfoTooltip text={accuracyTooltipContent(model1Data)} />
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="h-3 flex-1 rounded-full bg-gray-700">
                        <div
                          className="h-full rounded-full bg-green-500"
                          style={{
                            width: `${getAccuracyPercentage(model1Data)}%`,
                          }}
                        ></div>
                      </div>
                      <span className="text-sm font-medium">
                        {getAccuracyPercentage(model1Data)}%
                      </span>
                    </div>
                  </div>

                  {/* Explanation Text - Only show if we have model data */}
                  {model1Data && getModelExplanation(model1Data) && (
                    <div className="rounded-lg bg-gray-800/50 p-6">
                      <p className="mb-2 text-sm text-gray-400">
                        Model Explanation
                      </p>
                      <p className="whitespace-pre-wrap text-sm text-gray-200">
                        {getModelExplanation(model1Data)}
                      </p>
                    </div>
                  )}

                  {/* Add the LLM predictions display for the centralized model */}
                  {model1 === "regression" && model1Data && model1Data.models && (
                    <LLMPredictionsDisplay modelData={model1Data} />
                  )}

                  {/* Keep the existing LLM weights display for the confidence model */}
                  {model1 === "confidence" && model1Data && model1Data.models && (
                    <LLMWeightsDisplay modelData={model1Data} />
                  )}
                </>
              )}
            </div>
          </div>
        </div>

        {/* Model 2 Output */}
        <div className="flex-1">
          <div className="flex h-full flex-col rounded-xl bg-gray-800/30 p-6">
            <div className="flex-1 space-y-6">
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-bold">Model Prediction</h2>
                  <Select value={model2} onValueChange={handleModel2Change}>
                    <SelectTrigger className="w-60 rounded-full bg-purple-500/20 px-3 py-1 text-sm text-purple-400">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-gray-200 text-gray-900">
                      {AVAILABLE_MODELS.map((model) => (
                        <SelectItem
                          key={model.id}
                          value={model.id}
                          className="hover:bg-gray-300 focus:bg-gray-300"
                        >
                          {model.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Content section */}
              {isAppraisalLoading ? (
                <LoadingSkeleton />
              ) : (
                <>
                  {/* Price Prediction */}
                  <div className="rounded-lg bg-gray-800/50 p-6">
                    <p className="mb-2 text-sm text-gray-400">
                      Estimated Value
                    </p>
                    <p className="text-3xl font-bold text-purple-400">
                      {model2Data
                        ? `${getEthereumPrice(model2Data)} ETH ($${getUsdPrice(model2Data)})`
                        : "-.-- ETH"}
                    </p>
                  </div>

                  {/* Confidence Score */}
                  <div className="rounded-lg bg-gray-800/50 p-6">
                    <div className="mb-2 flex items-center text-sm text-gray-400">
                      Confidence Score
                      <InfoTooltip
                        text={confidenceTooltipContent(model2, model2Data)}
                      />
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="h-3 flex-1 rounded-full bg-gray-700">
                        <div
                          className="h-full rounded-full bg-purple-500"
                          style={{
                            width: `${getConfidencePercentage(model2Data)}%`,
                          }}
                        ></div>
                      </div>
                      <span className="text-sm font-medium">
                        {getConfidencePercentage(model2Data)}%
                      </span>
                    </div>
                  </div>

                  {/* Accuracy Score */}
                  <div className="rounded-lg bg-gray-800/50 p-6">
                    <div className="mb-2 flex items-center text-sm text-gray-400">
                      Accuracy Score
                      <InfoTooltip text={accuracyTooltipContent(model2Data)} />
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="h-3 flex-1 rounded-full bg-gray-700">
                        <div
                          className="h-full rounded-full bg-green-500"
                          style={{
                            width: `${getAccuracyPercentage(model2Data)}%`,
                          }}
                        ></div>
                      </div>
                      <span className="text-sm font-medium">
                        {getAccuracyPercentage(model2Data)}%
                      </span>
                    </div>
                  </div>

                  {/* Explanation Text - Only show if we have model data */}
                  {model2Data && getModelExplanation(model2Data) && (
                    <div className="rounded-lg bg-gray-800/50 p-6">
                      <p className="mb-2 text-sm text-gray-400">
                        Model Explanation
                      </p>
                      <p className="whitespace-pre-wrap text-sm text-gray-200">
                        {getModelExplanation(model2Data)}
                      </p>
                    </div>
                  )}

                  {/* Add the LLM predictions display for the centralized model */}
                  {model2 === "regression" && model2Data && model2Data.models && (
                    <LLMPredictionsDisplay modelData={model2Data} />
                  )}

                  {/* Keep the existing LLM weights display for the confidence model */}
                  {model2 === "confidence" && model2Data && model2Data.models && (
                    <LLMWeightsDisplay modelData={model2Data} />
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
