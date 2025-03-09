"use client"


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

interface NetworkAnimationProps {
  steps: ConsensusStep[];
  currentStep: number;
}

export function NetworkAnimation({ steps, currentStep }: NetworkAnimationProps) {
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

// Example consensus steps
export const defaultConsensusSteps: ConsensusStep[] = [
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
];

export type { ConsensusStep };