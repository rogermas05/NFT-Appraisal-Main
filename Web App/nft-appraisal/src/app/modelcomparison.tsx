"use client"

import { useState } from "react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select"
import type { ConsensusStep } from "./ConsensusAnimation"
import { defaultConsensusSteps, NetworkAnimation } from "./ConsensusAnimation"

// Available models for selection
const AVAILABLE_MODELS = [
  { id: "regression", name: "Centralized Aggregator" },
  { id: "neural", name: "Neural Network" },
  { id: "random_forest", name: "Random Forest" },
  { id: "ensemble", name: "Ensemble Model" },
  { id: "transformer", name: "Transformer Model" },
] as const

type ModelId = typeof AVAILABLE_MODELS[number]["id"]

export default function ModelComparison() {
  const [model1, setModel1] = useState<ModelId>("regression")
  const [model2, setModel2] = useState<ModelId>("neural")
  const [showAnimation1, setShowAnimation1] = useState(false)
  const [showAnimation2, setShowAnimation2] = useState(false)
  const [currentStep, setCurrentStep] = useState(0);
  const [consensusSteps, setConsensusSteps] = useState<ConsensusStep[]>(defaultConsensusSteps);

  // Remove the old useEffect and keep only the animation content
  const animationContent = (
    <div className="h-[300px] flex items-center justify-center">
      <NetworkAnimation steps={consensusSteps} currentStep={currentStep} />
    </div>
  );

  return (
    <div className="flex-1 flex gap-6 p-6">
      {/* Model 1 Output */}
      <div 
        className="flex-1 relative"
        style={{ perspective: '1000px' }}
      >
        <div 
          className={`h-full transition-transform duration-600`}
          style={{ 
            transformStyle: 'preserve-3d',
            transition: 'transform 0.6s',
            transform: showAnimation1 ? 'rotateY(180deg)' : 'rotateY(0deg)'
          }}
        >
          {/* Front side */}
          <div 
            className="absolute inset-0 w-full h-full bg-gray-800/30 rounded-xl p-6"
            style={{ backfaceVisibility: 'hidden' }}
          >
            <div className="space-y-6">
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-bold">Model Prediction</h2>
                  <Select value={model1} onValueChange={(value: ModelId) => setModel1(value)}>
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
                {/* Replace toggle with button - Front side Model 1 */}
                <div className="flex items-center gap-2">
                  <button
                    className="px-4 py-2 bg-blue-500/20 text-blue-400 rounded-full text-sm hover:bg-blue-500/30 transition-colors"
                    onClick={() => setShowAnimation1(!showAnimation1)}
                  >
                    Show Animation
                  </button>
                </div>
              </div>

              {!showAnimation1 ? (
                <>
                  {/* Price Prediction */}
                  <div className="bg-gray-800/50 rounded-lg p-6">
                    <p className="text-sm text-gray-400 mb-2">Estimated Value</p>
                    <p className="text-3xl font-bold text-blue-400">0.00 ETH</p>
                  </div>

                  {/* Confidence Score */}
                  <div className="bg-gray-800/50 rounded-lg p-6">
                    <p className="text-sm text-gray-400 mb-2">Confidence Score</p>
                    <div className="flex items-center gap-3">
                      <div className="flex-1 h-3 bg-gray-700 rounded-full">
                        <div className="h-full w-0 bg-blue-500 rounded-full"></div>
                      </div>
                      <span className="text-sm font-medium">0%</span>
                    </div>
                  </div>
                </>
              ) : (
                animationContent
              )}
            </div>
          </div>

          {/* Back side of Model 1 */}
          <div 
            className="absolute inset-0 w-full h-full bg-gray-800/30 rounded-xl p-6"
            style={{ 
              backfaceVisibility: 'hidden',
              transform: 'rotateY(180deg)'
            }}
          >
            <div className="flex flex-col h-full">
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-bold">Model Prediction</h2>
                  <Select value={model1} onValueChange={(value: ModelId) => setModel1(value)}>
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
                {/* Replace toggle with button - Back side Model 1 */}
                <div className="flex items-center gap-2">
                  <button
                    className="px-4 py-2 bg-blue-500/20 text-blue-400 rounded-full text-sm hover:bg-blue-500/30 transition-colors"
                    onClick={() => setShowAnimation1(!showAnimation1)}
                  >
                    Show Prediction
                  </button>
                </div>
              </div>
              <div className="flex-1 flex items-center justify-center mt-6">
                {animationContent}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Model 2 Output */}
      <div 
        className="flex-1 relative"
        style={{ perspective: '1000px' }}
      >
        <div 
          className={`h-full transition-transform duration-600`}
          style={{ 
            transformStyle: 'preserve-3d',
            transition: 'transform 0.6s',
            transform: showAnimation2 ? 'rotateY(180deg)' : 'rotateY(0deg)'
          }}
        >
          {/* Front side */}
          <div 
            className="absolute inset-0 w-full h-full bg-gray-800/30 rounded-xl p-6"
            style={{ backfaceVisibility: 'hidden' }}
          >
            <div className="space-y-6">
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-bold">Model Prediction</h2>
                  <Select value={model2} onValueChange={(value: ModelId) => setModel2(value)}>
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
                {/* Replace toggle with button - Front side Model 2 */}
                <div className="flex items-center gap-2">
                  <button
                    className="px-4 py-2 bg-purple-500/20 text-purple-400 rounded-full text-sm hover:bg-purple-500/30 transition-colors"
                    onClick={() => setShowAnimation2(!showAnimation2)}
                  >
                    Show Animation
                  </button>
                </div>
              </div>

              {!showAnimation2 ? (
                <>
                  {/* Price Prediction */}
                  <div className="bg-gray-800/50 rounded-lg p-6">
                    <p className="text-sm text-gray-400 mb-2">Estimated Value</p>
                    <p className="text-3xl font-bold text-purple-400">0.00 ETH</p>
                  </div>

                  {/* Confidence Score */}
                  <div className="bg-gray-800/50 rounded-lg p-6">
                    <p className="text-sm text-gray-400 mb-2">Confidence Score</p>
                    <div className="flex items-center gap-3">
                      <div className="flex-1 h-3 bg-gray-700 rounded-full">
                        <div className="h-full w-0 bg-purple-500 rounded-full"></div>
                      </div>
                      <span className="text-sm font-medium">0%</span>
                    </div>
                  </div>
                </>
              ) : (
                animationContent
              )}
            </div>
          </div>

          {/* Back side of Model 2 */}
          <div 
            className="absolute inset-0 w-full h-full bg-gray-800/30 rounded-xl p-6"
            style={{ 
              backfaceVisibility: 'hidden',
              transform: 'rotateY(180deg)'
            }}
          >
            <div className="flex flex-col h-full">
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-bold">Model Prediction</h2>
                  <Select value={model2} onValueChange={(value: ModelId) => setModel2(value)}>
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
                {/* Replace toggle with button - Back side Model 2 */}
                <div className="flex items-center gap-2">
                  <button
                    className="px-4 py-2 bg-purple-500/20 text-purple-400 rounded-full text-sm hover:bg-purple-500/30 transition-colors"
                    onClick={() => setShowAnimation2(!showAnimation2)}
                  >
                    Show Prediction
                  </button>
                </div>
              </div>
              <div className="flex-1 flex items-center justify-center mt-6">
                {animationContent}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
} 