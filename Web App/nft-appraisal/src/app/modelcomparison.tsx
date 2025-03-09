"use client"

import { Info } from "lucide-react"
import { useEffect, useState } from "react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select"
import type { ConsensusStep } from "./ConsensusAnimation"
import { defaultConsensusSteps, NetworkAnimation } from "./ConsensusAnimation"
import { useNFTData } from './NftDataContext'

// Available models for selection
const AVAILABLE_MODELS = [
  { id: "regression", name: "Centralized Aggregator" },
  { id: "confidence", name: "Confidence Adjusted Aggregator" },
  { id: "singular", name: "Singular Model Approach" },
] as const

type ModelId = typeof AVAILABLE_MODELS[number]["id"]

export default function ModelComparison() {
  const [model1, setModel1] = useState<ModelId>("regression")
  const [model2, setModel2] = useState<ModelId>("confidence")
  const [showAnimation1, setShowAnimation1] = useState(false)
  const [showAnimation2, setShowAnimation2] = useState(false)
  const [currentStep, setCurrentStep] = useState(0);
  const [consensusSteps, setConsensusSteps] = useState<ConsensusStep[]>(defaultConsensusSteps);
  const { nftData, isAppraisalLoading, selectedModels, setSelectedModels } = useNFTData();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Get model-specific data instead of just appraisalData
  const model1Data = nftData?.modelResults?.[model1];
  const model2Data = nftData?.modelResults?.[model2];
  
  // Updated helper functions to handle different API response formats
  const getEthereumPrice = (modelData: any): string => {
    if (!modelData) return "-.--";
    
    // Direct ethereum price if available
    if (modelData.ethereum_price_usd !== undefined) {
      return modelData.ethereum_price_usd.toFixed(2);
    }
    
    // If the API only returns USD price (like confidence API), estimate ETH price
    // Assuming current ETH price of ~$2,500 for conversion
    if (modelData.price !== undefined) {
      const estimatedEthPrice = modelData.price / 2500;
      return estimatedEthPrice.toFixed(4);
    }
    
    return "-.--";
  };

  const getUsdPrice = (modelData: any): string => {
    if (!modelData) return "-.--";
    
    // Direct USD price
    if (modelData.price !== undefined) {
      return modelData.price.toFixed(2);
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
    
    return 0;
  };

  const getAccuracyPercentage = (modelData: any) => {
    if (!modelData || modelData.accuracy === undefined) return 0;
    return Math.round(modelData.accuracy * 100);
  };

  const getModelExplanation = (modelData: any) => {
    if (!modelData) return "";
    
    // Different APIs use different field names for explanation text
    if (modelData.text) return modelData.text;
    if (modelData.explanation) return modelData.explanation;
    
    return "";
  };

  // Create confidence tooltip content with standard deviation
  const confidenceTooltipContent = (modelId: ModelId, modelData: any) => {
    const baseText = "Confidence score represents how certain the model is about its prediction. Higher values indicate greater confidence in the estimated value.";
    
    if (modelData && modelData.standard_deviation) {
      return (
        <>
          {baseText}
          <div className="mt-2 pt-2 border-t border-gray-600">
            <span className="font-semibold">Standard Deviation:</span> {modelData.standard_deviation.toFixed(2)}
            <p className="mt-1">This value shows how much the predictions from different models vary. Lower standard deviation indicates better agreement between models.</p>
          </div>
        </>
      );
    }
    
    return baseText;
  };

  // Get contract address and token ID from nftData
  const contractAddress = nftData?.contractAddress;
  const tokenId = nftData?.tokenId;

  // Update this useEffect to sync model selections with context
  useEffect(() => {
    setSelectedModels([model1, model2]);
  }, [model1, model2, setSelectedModels]);

  // Loading skeleton component
  const LoadingSkeleton = () => (
    <>
      {/* Price Prediction Skeleton */}
      <div className="bg-gray-800/50 rounded-lg p-6">
        <p className="text-sm text-gray-400 mb-2">Estimated Value</p>
        <div className="h-9 bg-gray-700 rounded-md animate-pulse w-2/3"></div>
      </div>

      {/* Confidence Score Skeleton */}
      <div className="bg-gray-800/50 rounded-lg p-6">
        <p className="text-sm text-gray-400 mb-2">Confidence Score</p>
        <div className="flex items-center gap-3">
          <div className="flex-1 h-3 bg-gray-700 rounded-full animate-pulse"></div>
          <div className="h-5 w-10 bg-gray-700 rounded-md animate-pulse"></div>
        </div>
      </div>

      {/* Accuracy Score Skeleton */}
      <div className="bg-gray-800/50 rounded-lg p-6">
        <p className="text-sm text-gray-400 mb-2">Accuracy Score</p>
        <div className="flex items-center gap-3">
          <div className="flex-1 h-3 bg-gray-700 rounded-full animate-pulse"></div>
          <div className="h-5 w-10 bg-gray-700 rounded-md animate-pulse"></div>
        </div>
      </div>

      {/* Explanation Text Skeleton - Make this more flexible */}
      <div className="bg-gray-800/50 rounded-lg p-6">
        <p className="text-sm text-gray-400 mb-2">Model Explanation</p>
        <div className="space-y-2">
          <div className="h-4 bg-gray-700 rounded-md animate-pulse w-full"></div>
          <div className="h-4 bg-gray-700 rounded-md animate-pulse w-5/6"></div>
          <div className="h-4 bg-gray-700 rounded-md animate-pulse w-4/6"></div>
          <div className="h-4 bg-gray-700 rounded-md animate-pulse w-3/4"></div>
          <div className="h-4 bg-gray-700 rounded-md animate-pulse w-2/3"></div>
        </div>
      </div>
    </>
  );

  // Remove the old useEffect and keep only the animation content
  const animationContent = (
    <div className="h-[300px] flex items-center justify-center">
      <NetworkAnimation steps={consensusSteps} currentStep={currentStep} />
    </div>
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
  const InfoTooltip = ({ text, children }: { text: React.ReactNode, children?: React.ReactNode }) => (
    <div className="group relative inline-block ml-1">
      <Info size={16} className="text-gray-400 hover:text-gray-300 cursor-help" />
      <div className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 w-64 p-2 bg-gray-700 text-xs text-gray-200 rounded-md shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-10">
        {text}
        {children}
        <div className="absolute left-1/2 -translate-x-1/2 top-full -mt-1 border-4 border-transparent border-t-gray-700"></div>
      </div>
    </div>
  );

  return (
    <div className="flex-1 flex flex-col gap-6 p-6">
      {/* Error message toast */}
      {errorMessage && (
        <div className="fixed top-4 right-4 z-50 bg-red-500 text-white px-4 py-2 rounded-md shadow-lg animate-in fade-in slide-in-from-top-5 duration-300">
          {errorMessage}
        </div>
      )}
      
      <div className="flex flex-1 gap-6">
        {/* Model 1 Output */}
        <div className="flex-1 relative">
          {!showAnimation1 ? (
            <div className="h-full bg-gray-800/30 rounded-xl p-6 flex flex-col">
              <div className="space-y-6 flex-1">
                <div className="flex flex-col gap-3">
                  <div className="flex items-center justify-between">
                    <h2 className="text-xl font-bold">Model Prediction</h2>
                    <Select value={model1} onValueChange={handleModel1Change}>
                      <SelectTrigger className="px-3 py-1 bg-blue-500/20 text-blue-400 rounded-full text-sm w-60">
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
                  <div className="flex items-center gap-2">
                    <button
                      className="px-4 py-2 bg-blue-500/20 text-blue-400 rounded-full text-sm hover:bg-blue-500/30 transition-colors"
                      onClick={() => setShowAnimation1(!showAnimation1)}
                    >
                      Show Animation
                    </button>
                  </div>
                </div>

                {/* Content section - Now show loading for any model when loading is active */}
                {isAppraisalLoading ? (
                  <LoadingSkeleton />
                ) : (
                  <>
                    {/* Price Prediction */}
                    <div className="bg-gray-800/50 rounded-lg p-6">
                      <p className="text-sm text-gray-400 mb-2">Estimated Value</p>
                      <p className="text-3xl font-bold text-blue-400">
                        {model1Data ? 
                          `${getEthereumPrice(model1Data)} ETH ($${getUsdPrice(model1Data)})` : 
                          "-.-- ETH"}
                      </p>
                    </div>

                    {/* Confidence Score */}
                    <div className="bg-gray-800/50 rounded-lg p-6">
                      <div className="text-sm text-gray-400 mb-2 flex items-center">
                        Confidence Score
                        <InfoTooltip text={confidenceTooltipContent(model1, model1Data)} />
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="flex-1 h-3 bg-gray-700 rounded-full">
                          <div 
                            className="h-full bg-blue-500 rounded-full"
                            style={{ width: `${getConfidencePercentage(model1Data)}%` }}
                          ></div>
                        </div>
                        <span className="text-sm font-medium">
                          {getConfidencePercentage(model1Data)}%
                        </span>
                      </div>
                    </div>

                    {/* Accuracy Score */}
                    <div className="bg-gray-800/50 rounded-lg p-6">
                      <div className="text-sm text-gray-400 mb-2 flex items-center">
                        Accuracy Score
                        <InfoTooltip text="Accuracy score measures how close the model's predictions have been to actual sale prices historically. Higher values indicate better predictive performance." />
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="flex-1 h-3 bg-gray-700 rounded-full">
                          <div 
                            className="h-full bg-green-500 rounded-full"
                            style={{ width: `${getAccuracyPercentage(model1Data)}%` }}
                          ></div>
                        </div>
                        <span className="text-sm font-medium">
                          {getAccuracyPercentage(model1Data)}%
                        </span>
                      </div>
                    </div>

                    {/* Explanation Text - Only show if we have model data */}
                    {model1Data && getModelExplanation(model1Data) && (
                      <div className="bg-gray-800/50 rounded-lg p-6">
                        <p className="text-sm text-gray-400 mb-2">Model Explanation</p>
                        <p className="text-sm text-gray-200 whitespace-pre-wrap">
                          {getModelExplanation(model1Data)}
                        </p>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          ) : (
            <div className="h-full bg-gray-800/30 rounded-xl p-6 flex items-center justify-center">
              <NetworkAnimation 
                contractAddress={contractAddress}
                tokenId={tokenId}
              />
            </div>
          )}
        </div>

        {/* Model 2 Output */}
        <div className="flex-1 relative">
          {!showAnimation2 ? (
            <div className="h-full bg-gray-800/30 rounded-xl p-6 flex flex-col">
              <div className="space-y-6 flex-1">
                <div className="flex flex-col gap-3">
                  <div className="flex items-center justify-between">
                    <h2 className="text-xl font-bold">Model Prediction</h2>
                    <Select value={model2} onValueChange={handleModel2Change}>
                      <SelectTrigger className="px-3 py-1 bg-purple-500/20 text-purple-400 rounded-full text-sm w-60">
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
                  <div className="flex items-center gap-2">
                    <button
                      className="px-4 py-2 bg-purple-500/20 text-purple-400 rounded-full text-sm hover:bg-purple-500/30 transition-colors"
                      onClick={() => setShowAnimation2(!showAnimation2)}
                    >
                      Show Animation
                    </button>
                  </div>
                </div>

                {/* Content section - Now show loading for any model when loading is active */}
                {isAppraisalLoading ? (
                  <LoadingSkeleton />
                ) : (
                  <>
                    {/* Price Prediction */}
                    <div className="bg-gray-800/50 rounded-lg p-6">
                      <p className="text-sm text-gray-400 mb-2">Estimated Value</p>
                      <p className="text-3xl font-bold text-purple-400">
                        {model2Data ? 
                          `${getEthereumPrice(model2Data)} ETH ($${getUsdPrice(model2Data)})` : 
                          "-.-- ETH"}
                      </p>
                    </div>

                    {/* Confidence Score */}
                    <div className="bg-gray-800/50 rounded-lg p-6">
                      <div className="text-sm text-gray-400 mb-2 flex items-center">
                        Confidence Score
                        <InfoTooltip text={confidenceTooltipContent(model2, model2Data)} />
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="flex-1 h-3 bg-gray-700 rounded-full">
                          <div 
                            className="h-full bg-purple-500 rounded-full"
                            style={{ width: `${getConfidencePercentage(model2Data)}%` }}
                          ></div>
                        </div>
                        <span className="text-sm font-medium">
                          {getConfidencePercentage(model2Data)}%
                        </span>
                      </div>
                    </div>

                    {/* Accuracy Score */}
                    <div className="bg-gray-800/50 rounded-lg p-6">
                      <div className="text-sm text-gray-400 mb-2 flex items-center">
                        Accuracy Score
                        <InfoTooltip text="Accuracy score measures how close the model's predictions have been to actual sale prices historically. Higher values indicate better predictive performance." />
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="flex-1 h-3 bg-gray-700 rounded-full">
                          <div 
                            className="h-full bg-green-500 rounded-full"
                            style={{ width: `${getAccuracyPercentage(model2Data)}%` }}
                          ></div>
                        </div>
                        <span className="text-sm font-medium">
                          {getAccuracyPercentage(model2Data)}%
                        </span>
                      </div>
                    </div>

                    {/* Explanation Text - Only show if we have model data */}
                    {model2Data && getModelExplanation(model2Data) && (
                      <div className="bg-gray-800/50 rounded-lg p-6">
                        <p className="text-sm text-gray-400 mb-2">Model Explanation</p>
                        <p className="text-sm text-gray-200 whitespace-pre-wrap">
                          {getModelExplanation(model2Data)}
                        </p>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          ) : (
            <div className="h-full bg-gray-800/30 rounded-xl p-6 flex items-center justify-center">
              <NetworkAnimation 
                contractAddress={contractAddress}
                tokenId={tokenId}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
} 
