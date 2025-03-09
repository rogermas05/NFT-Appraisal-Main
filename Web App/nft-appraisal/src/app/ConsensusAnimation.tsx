"use client";

import { useEffect, useState, useRef } from "react";

type Node = {
  id: string;
  x: number;
  y: number;
  active: boolean;
  value?: number;
};

type Connection = {
  from: string;
  to: string;
  active: boolean;
  value?: number;
};

type LogEntry = {
  message: string;
  type: "info" | "error" | "warning" | "success";
  timestamp: string;
};

type StreamStats = {
  aggregatedPrice?: number;
  standardDeviation?: number;
  confidence?: number;
  finalResult?: any;
};

interface NetworkAnimationProps {
  contractAddress?: string;
  tokenId?: string;
}

// Add this type definition
type ConsensusStep = {
  activeNodes: string[];
  activeConnections: string[];
  nodeValues?: Record<string, number>;
  connectionValues?: Record<string, number>;
};

export function NetworkAnimation({
  contractAddress,
  tokenId,
}: NetworkAnimationProps) {
  // State for nodes and connections
  const [nodes, setNodes] = useState<Node[]>([
    // Three LLM nodes on top
    { id: "llm1", x: 75, y: 50, active: false },
    { id: "llm2", x: 150, y: 50, active: false },
    { id: "llm3", x: 225, y: 50, active: false },
    // Aggregator node at bottom center
    { id: "aggregator", x: 150, y: 200, active: false },
  ]);

  const [connections, setConnections] = useState<Connection[]>([
    // Connect each LLM to the aggregator
    { from: "llm1", to: "aggregator", active: false },
    { from: "llm2", to: "aggregator", active: false },
    { from: "llm3", to: "aggregator", active: false },
  ]);

  // State for logs and statistics
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [stats, setStats] = useState<StreamStats>({});
  const [currentStage, setCurrentStage] = useState<string>("idle");

  // Reference to the EventSource
  const eventSourceRef = useRef<EventSource | null>(null);

  // Function to add a log entry
  const addLog = (
    message: string,
    type: "info" | "error" | "warning" | "success",
  ) => {
    setLogs((prev) => [
      { message, type, timestamp: new Date().toISOString() },
      ...prev.slice(0, 19), // Keep only the 20 most recent logs
    ]);
  };

  // Connect to the streaming API when contractAddress and tokenId are provided
  useEffect(() => {
    if (!contractAddress || !tokenId) {
      console.log(
        "Missing contractAddress or tokenId, not connecting to stream",
      );
      return;
    }

    console.log(`Connecting to stream for ${contractAddress}:${tokenId}`);

    // Reset state
    setNodes((nodes) =>
      nodes.map((node) => ({ ...node, active: false, value: undefined })),
    );
    setConnections((conns) =>
      conns.map((conn) => ({ ...conn, active: false, value: undefined })),
    );
    setLogs([]);
    setStats({});
    setCurrentStage("connecting");

    // Close any existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    addLog(
      `Connecting to appraisal stream for ${contractAddress}:${tokenId}...`,
      "info",
    );

    // Create new EventSource connection with the correct URL format
    // Using the same base URL as in header.tsx
    const url = `http://127.0.0.1:8080/appraise/stream?contract_address=${encodeURIComponent(contractAddress)}&token_id=${encodeURIComponent(tokenId)}`;
    console.log(`Stream URL: ${url}`);

    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    // Add onerror handler to log connection issues
    eventSource.onerror = (error) => {
      console.error("EventSource error:", error);
      addLog("Connection error with streaming API", "error");
    };

    // Handle connection open
    eventSource.addEventListener("connect", (event) => {
      setCurrentStage("connected");
      addLog("Connected to appraisal stream", "success");
    });

    // Handle stage updates
    eventSource.addEventListener("stage", (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data);
        const stageName = data.data?.name || "unknown";
        const description = data.data?.description || "";

        setCurrentStage(stageName);
        addLog(`Stage: ${description || stageName}`, "info");

        // Update node activation based on stage
        if (stageName.includes("query") || stageName === "initial_round") {
          // Activate LLM nodes during querying
          setNodes((nodes) =>
            nodes.map((node) => ({
              ...node,
              active: node.id.startsWith("llm"),
            })),
          );
          setConnections((conns) =>
            conns.map((conn) => ({ ...conn, active: false })),
          );
        } else if (
          stageName.includes("aggregat") ||
          stageName === "improvement_round"
        ) {
          // Activate aggregator and connections during aggregation
          setNodes((nodes) =>
            nodes.map((node) => ({
              ...node,
              active: node.id === "aggregator",
            })),
          );
          setConnections((conns) =>
            conns.map((conn) => ({ ...conn, active: true })),
          );
        } else if (stageName === "complete") {
          // Activate all nodes and connections when complete
          setNodes((nodes) => nodes.map((node) => ({ ...node, active: true })));
          setConnections((conns) =>
            conns.map((conn) => ({ ...conn, active: true })),
          );
        }
      } catch (e) {
        console.error("Error parsing stage event:", e);
      }
    });

    // Handle model responses
    eventSource.addEventListener("model_responses", (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data);
        const responses = data.data?.responses || {};

        // Update LLM node values with model responses
        const nodeUpdates: Record<string, number> = {};
        let index = 1;

        for (const [modelId, response] of Object.entries(responses)) {
          try {
            // Try to extract a numeric value from the response
            const responseStr = String(response);
            const priceMatch = responseStr.match(/(\d+(\.\d+)?)/);
            if (priceMatch && index <= 3) {
              const price = parseFloat(priceMatch[0]);
              nodeUpdates[`llm${index}`] = price;
              index++;
            }
          } catch (e) {
            console.error("Error parsing model response:", e);
          }
        }

        // Update node values
        if (Object.keys(nodeUpdates).length > 0) {
          setNodes((nodes) =>
            nodes.map((node) => ({
              ...node,
              value:
                nodeUpdates[node.id] !== undefined
                  ? nodeUpdates[node.id]
                  : node.value,
            })),
          );
        }

        addLog(
          `Received responses from ${Object.keys(responses).length} models`,
          "info",
        );
      } catch (e) {
        console.error("Error parsing model_responses event:", e);
      }
    });

    // Handle initial statistics
    eventSource.addEventListener("initial_statistics", (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data);
        const stats = data.data || {};

        setStats((prev) => ({
          ...prev,
          aggregatedPrice: stats.aggregated_price,
          standardDeviation: stats.standard_deviation,
          confidence: stats.confidence,
        }));

        // Update aggregator node value
        if (stats.aggregated_price) {
          setNodes((nodes) =>
            nodes.map((node) =>
              node.id === "aggregator"
                ? { ...node, value: stats.aggregated_price }
                : node,
            ),
          );
        }

        addLog(
          `Initial consensus: $${stats.aggregated_price?.toFixed(2) || "unknown"}`,
          "info",
        );
      } catch (e) {
        console.error("Error parsing initial_statistics event:", e);
      }
    });

    // Handle final statistics
    eventSource.addEventListener("final_statistics", (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data);
        const stats = data.data || {};

        setStats((prev) => ({
          ...prev,
          aggregatedPrice: stats.aggregated_price,
          standardDeviation: stats.standard_deviation,
          confidence: stats.confidence,
        }));

        // Update aggregator node value
        if (stats.aggregated_price) {
          setNodes((nodes) =>
            nodes.map((node) =>
              node.id === "aggregator"
                ? { ...node, value: stats.aggregated_price }
                : node,
            ),
          );
        }

        addLog(
          `Final consensus: $${stats.aggregated_price?.toFixed(2) || "unknown"}`,
          "success",
        );
      } catch (e) {
        console.error("Error parsing final_statistics event:", e);
      }
    });

    // Handle final result
    eventSource.addEventListener("final_result", (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data);
        const result = data.data || {};

        setStats((prev) => ({
          ...prev,
          finalResult: result,
        }));

        addLog(
          `Appraisal complete: $${result.price?.toFixed(2) || "unknown"}`,
          "success",
        );
      } catch (e) {
        console.error("Error parsing final_result event:", e);
      }
    });

    // Handle log messages
    eventSource.addEventListener("log", (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data);
        const message = data.data?.message || "";
        const color = data.data?.color || "default";

        // Map color to log type
        let type: "info" | "error" | "warning" | "success" = "info";
        if (color === "red") type = "error";
        else if (color === "yellow") type = "warning";
        else if (color === "green") type = "success";

        addLog(message, type);
      } catch (e) {
        console.error("Error parsing log event:", e);
      }
    });

    // Handle errors
    eventSource.addEventListener("error", (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data);
        const message = data.data?.message || "Unknown error";

        addLog(`Error: ${message}`, "error");
      } catch (e) {
        console.error("Error parsing error event:", e);
        addLog("An error occurred in the appraisal process", "error");
      }
    });

    // Handle process end
    eventSource.addEventListener("process_end", (event) => {
      addLog("Process completed", "success");
      eventSource.close();
      eventSourceRef.current = null;
    });

    // Cleanup function
    return () => {
      console.log("Cleaning up EventSource connection");
      eventSource.close();
      eventSourceRef.current = null;
    };
  }, [contractAddress, tokenId]);

  return (
    <div className="flex h-full w-full flex-col gap-4">
      {/* Animation */}
      <div className="flex flex-1 items-center justify-center">
        <svg width="300" height="300" className="rounded-lg bg-gray-900/50">
          {/* Draw connections */}
          {connections.map((conn) => {
            const fromNode = nodes.find((n) => n.id === conn.from)!;
            const toNode = nodes.find((n) => n.id === conn.to)!;
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
          {nodes.map((node) => (
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

          {/* Current stage indicator */}
          <text
            x="150"
            y="270"
            fill="#9CA3AF"
            textAnchor="middle"
            fontSize="14"
          >
            {currentStage}
          </text>
        </svg>
      </div>

      {/* Statistics panel */}
      <div className="rounded-lg bg-gray-900/50 p-3 text-sm">
        <h3 className="mb-2 font-medium text-white">Statistics</h3>
        <div className="grid grid-cols-2 gap-2">
          {stats.aggregatedPrice !== undefined && (
            <div className="col-span-2">
              <span className="text-gray-400">Current Price Estimate:</span>{" "}
              <span className="font-medium text-white">
                ${stats.aggregatedPrice.toFixed(2)}
              </span>
            </div>
          )}

          {stats.standardDeviation !== undefined && (
            <div>
              <span className="text-gray-400">Std Deviation:</span>{" "}
              <span className="text-white">
                ${stats.standardDeviation.toFixed(2)}
              </span>
            </div>
          )}

          {stats.confidence !== undefined && (
            <div>
              <span className="text-gray-400">Confidence:</span>{" "}
              <span className="text-white">
                {(stats.confidence * 100).toFixed(0)}%
              </span>
            </div>
          )}

          {stats.finalResult?.price !== undefined && (
            <div className="col-span-2 mt-1 border-t border-gray-700 pt-1">
              <span className="text-gray-400">Final Appraisal:</span>{" "}
              <span className="font-medium text-white">
                ${stats.finalResult.price.toFixed(2)}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Log panel */}
      <div className="h-40 overflow-y-auto rounded-lg bg-gray-900/50 p-3">
        <h3 className="mb-2 font-medium text-white">Process Log</h3>
        <div className="space-y-1 text-sm">
          {logs.map((log, index) => (
            <div
              key={index}
              className={` ${log.type === "error" ? "text-red-400" : ""} ${log.type === "warning" ? "text-yellow-400" : ""} ${log.type === "success" ? "text-green-400" : ""} ${log.type === "info" ? "text-gray-300" : ""} `}
            >
              {log.message}
            </div>
          ))}
          {logs.length === 0 && (
            <div className="italic text-gray-500">No logs yet</div>
          )}
        </div>
      </div>
    </div>
  );
}

// Example consensus steps
export const defaultConsensusSteps: ConsensusStep[] = [
  {
    activeNodes: ["llm1", "llm2", "llm3"],
    activeConnections: [],
    nodeValues: { llm1: 0.3, llm2: 0.5, llm3: 0.7 },
  },
  {
    activeNodes: ["llm1", "llm2", "llm3", "aggregator"],
    activeConnections: [
      "llm1-aggregator",
      "llm2-aggregator",
      "llm3-aggregator",
    ],
    nodeValues: { llm1: 0.3, llm2: 0.5, llm3: 0.7, aggregator: 0.5 },
    connectionValues: {
      "llm1-aggregator": 0.3,
      "llm2-aggregator": 0.5,
      "llm3-aggregator": 0.7,
    },
  },
];

export type { ConsensusStep };
