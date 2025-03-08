"use client"

import { useState } from "react"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "../components/ui/select"

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

  return (
    <div className="flex-1 flex gap-6 p-6">
      {/* Model 1 Output */}
      <div className="flex-1 bg-gray-800/30 rounded-xl p-6">
        <div className="space-y-6">
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold">Model Prediction</h2>
              <Select value={model1} onValueChange={(value: ModelId) => setModel1(value)}>
                <SelectTrigger className="px-3 py-1 bg-blue-500/20 text-blue-400 rounded-full text-sm w-52">
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

        </div>
      </div>

      {/* Model 2 Output */}
      <div className="flex-1 bg-gray-800/30 rounded-xl p-6">
        <div className="space-y-6">
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold">Model Prediction</h2>
              <Select value={model2} onValueChange={(value: ModelId) => setModel2(value)}>
                <SelectTrigger className="px-3 py-1 bg-purple-500/20 text-purple-400 rounded-full text-sm w-52">
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

        </div>
      </div>
    </div>
  )
} 