"use client"

import { useEffect, useState } from "react"
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

// Add these types for our animation
type Node = {
  id: string;
  x: number;
  y: number;
  active: boolean;
  value?: number;
}

type Connection = {
  from: string;
  to: string;
  active: boolean;
  value?: number;
}

type ConsensusStep = {
  activeNodes: string[];
  activeConnections: string[];
  nodeValues?: Record<string, number>;
  connectionValues?: Record<string, number>;
}

function NetworkAnimation({ steps, currentStep }: { steps: ConsensusStep[], currentStep: number }) {
  // Define initial network structure with new layout
  const nodes: Node[] = [
    // Three LLM nodes on top
    { id: 'llm1', x: 75, y: 50, active: false },
    { id: 'llm2', x: 150, y: 50, active: false },
    { id: 'llm3', x: 225, y: 50, active: false },
    // Aggregator node at bottom center
    { id: 'aggregator', x: 150, y: 200, active: false },
  ];

  const connections: Connection[] = [
    // Connect each LLM to the aggregator
    { from: 'llm1', to: 'aggregator', active: false },
    { from: 'llm2', to: 'aggregator', active: false },
    { from: 'llm3', to: 'aggregator', active: false },
  ];

  // Update active states based on current step
  const currentStepData = steps[currentStep];
  if (currentStepData) {
    nodes.forEach(node => {
      node.active = currentStepData.activeNodes.includes(node.id);
      node.value = currentStepData.nodeValues?.[node.id];
    });
    
    connections.forEach(conn => {
      const connId = `${conn.from}-${conn.to}`;
      conn.active = currentStepData.activeConnections.includes(connId);
      conn.value = currentStepData.connectionValues?.[connId];
    });
  }

  return (
    <svg width="300" height="300" className="bg-gray-900/50 rounded-lg">
      {/* Draw connections */}
      {connections.map(conn => {
        const fromNode = nodes.find(n => n.id === conn.from)!;
        const toNode = nodes.find(n => n.id === conn.to)!;
        return (
          <g key={`${conn.from}-${conn.to}`}>
            <line
              x1={fromNode.x}
              y1={fromNode.y}
              x2={toNode.x}
              y2={toNode.y}
              stroke={conn.active ? "#8B5CF6" : "#374151"}
              strokeWidth="2"
              className="transition-colors duration-300"
            />
            {conn.value && (
              <text
                x={(fromNode.x + toNode.x) / 2}
                y={(fromNode.y + toNode.y) / 2 - 5}
                fill="#9CA3AF"
                textAnchor="middle"
                fontSize="12"
              >
                {conn.value.toFixed(2)}
              </text>
            )}
          </g>
        );
      })}
      
      {/* Draw nodes */}
      {nodes.map(node => (
        <g key={node.id}>
          <circle
            cx={node.x}
            cy={node.y}
            r="20"
            fill={node.active ? "#8B5CF6" : "#374151"}
            className="transition-colors duration-300"
          />
          <text
            x={node.x}
            y={node.y - 30}
            fill="#9CA3AF"
            textAnchor="middle"
            fontSize="14"
          >
            {node.id.toUpperCase()}
          </text>
          {node.value && (
            <text
              x={node.x}
              y={node.y}
              fill="#ffffff"
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize="12"
            >
              {node.value.toFixed(2)}
            </text>
          )}
        </g>
      ))}
    </svg>
  );
}

export default function ModelComparison() {
  const [model1, setModel1] = useState<ModelId>("regression")
  const [model2, setModel2] = useState<ModelId>("neural")
  const [showAnimation1, setShowAnimation1] = useState(false)
  const [showAnimation2, setShowAnimation2] = useState(false)
  const [currentStep, setCurrentStep] = useState(0);
  const [consensusSteps, setConsensusSteps] = useState<ConsensusStep[]>([]);

  // Simulated webhook response handler
  useEffect(() => {
    const simulatedSteps: ConsensusStep[] = [
      {
        activeNodes: ['llm1', 'llm2', 'llm3'],
        activeConnections: [],
        nodeValues: { llm1: 0.3, llm2: 0.5, llm3: 0.7 }
      },
      {
        activeNodes: ['llm1', 'llm2', 'llm3', 'aggregator'],
        activeConnections: ['llm1-aggregator', 'llm2-aggregator', 'llm3-aggregator'],
        nodeValues: { llm1: 0.3, llm2: 0.5, llm3: 0.7, aggregator: 0.5 },
        connectionValues: { 
          'llm1-aggregator': 0.3,
          'llm2-aggregator': 0.5,
          'llm3-aggregator': 0.7
        }
      },
      // Add more steps as needed
    ];
    setConsensusSteps(simulatedSteps);
  }, []);

  // Replace the animation placeholder with our network animation
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