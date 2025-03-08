"use client"

import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'

type ModelAnimationProps = {
  modelId: string
  isPlaying: boolean
}

export function ModelAnimation({ modelId, isPlaying }: ModelAnimationProps) {
  const [metrics, setMetrics] = useState({
    accuracy: 0,
    consensus: 0,
    iterations: 0,
  })

  // Simulate metrics updates
  useEffect(() => {
    if (isPlaying) {
      const interval = setInterval(() => {
        setMetrics(prev => ({
          accuracy: Math.min(100, prev.accuracy + Math.random() * 5),
          consensus: Math.min(100, prev.consensus + Math.random() * 3),
          iterations: prev.iterations + 1,
        }))
      }, 1000)
      return () => clearInterval(interval)
    }
  }, [isPlaying])

  return (
    <AnimatePresence>
      {isPlaying && (
        <motion.div
          initial={{ rotateY: 0 }}
          animate={{ rotateY: [0, -180] }}
          exit={{ rotateY: 0 }}
          transition={{ 
            duration: 1,
            repeat: Infinity,
            repeatDelay: 2,
            ease: "easeInOut"
          }}
          style={{ 
            perspective: "1200px",
            transformStyle: "preserve-3d",
          }}
          className="w-full bg-gray-900/50 rounded-xl p-6 backdrop-blur-sm"
        >
          {/* Page Animation Container */}
          <div className="relative h-60 w-full">
            {/* Front Page */}
            <motion.div
              className="absolute inset-0 bg-gray-800 rounded-xl shadow-xl"
              style={{
                backfaceVisibility: "hidden",
                transformStyle: "preserve-3d",
              }}
            />
            
            {/* Back Page */}
            <motion.div
              className="absolute inset-0 bg-gray-800 rounded-xl shadow-xl"
              style={{
                backfaceVisibility: "hidden",
                transform: "rotateY(180deg)",
                transformStyle: "preserve-3d",
              }}
            />
          </div>

          {/* Floating Metrics */}
          <motion.div 
            className="mt-6 space-y-4"
            animate={{
              y: [0, -10, 0],
              opacity: [0.5, 1, 0.5],
            }}
            transition={{
              duration: 2,
              repeat: Infinity,
              ease: "easeInOut"
            }}
          >
            <MetricBar 
              label="Processing" 
              value={metrics.consensus} 
              color="blue" 
            />
            <MetricBar 
              label="Confidence" 
              value={metrics.accuracy} 
              color="green" 
            />
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">Analysis Phase</span>
              <span className="text-white font-mono">{metrics.iterations}</span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function MetricBar({ label, value, color }: { label: string, value: number, color: string }) {
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-sm">
        <span className="text-gray-400">{label}</span>
        <span className="text-white">{value.toFixed(1)}%</span>
      </div>
      <motion.div 
        className="h-2 bg-gray-800 rounded-full overflow-hidden"
      >
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${value}%` }}
          transition={{ duration: 0.5 }}
          className={`h-full bg-${color}-500`}
        />
      </motion.div>
    </div>
  )
}

function getModelAnimation(modelId: string) {
  switch (modelId) {
    case 'regression':
      return (
        <motion.div className="grid grid-cols-3 gap-4">
          {Array(9).fill(0).map((_, i) => (
            <motion.div
              key={i}
              animate={{
                scale: [1, 1.2, 1],
                opacity: [0.5, 1, 0.5],
              }}
              transition={{
                duration: 2,
                repeat: Infinity,
                delay: i * 0.2,
              }}
              className="w-4 h-4 bg-blue-500 rounded-full"
            />
          ))}
        </motion.div>
      )
    
    case 'neural':
      return (
        <motion.div className="relative w-40 h-40">
          {Array(12).fill(0).map((_, i) => (
            <motion.div
              key={i}
              animate={{
                rotate: 360,
                scale: [1, 1.2, 1],
              }}
              transition={{
                duration: 3,
                repeat: Infinity,
                delay: i * 0.2,
              }}
              className="absolute top-1/2 left-1/2 w-2 h-2 bg-purple-500 rounded-full"
              style={{
                transform: `rotate(${i * 30}deg) translateY(-20px)`,
              }}
            />
          ))}
        </motion.div>
      )
    
    // Add more model-specific animations...
    default:
      return (
        <div className="text-gray-400">
          Loading animation...
        </div>
      )
  }
} 