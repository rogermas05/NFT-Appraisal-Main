"use client"

export default function SideInfo() {
  return (
    <div className="w-96 border-l border-gray-700 min-h-full p-6">
      <div className="space-y-6">
        {/* NFT Image */}
        <div className="aspect-square w-full bg-gray-800 rounded-lg flex items-center justify-center">
          <span className="text-gray-400">NFT Image</span>
        </div>
        
        {/* NFT Metadata */}
        <div className="space-y-4">
          <h2 className="text-xl font-bold">NFT Details</h2>
          
          <div className="space-y-2">
            <div className="bg-gray-800/50 p-4 rounded-lg">
              <p className="text-sm text-gray-400">Collection Name</p>
              <p className="font-medium">-</p>
            </div>
                        
            <div className="bg-gray-800/50 p-4 rounded-lg">
              <p className="text-sm text-gray-400">Collection address</p>
              <p className="font-medium">-</p>
            </div>
            
            <div className="bg-gray-800/50 p-4 rounded-lg">
              <p className="text-sm text-gray-400">Token ID</p>
              <p className="font-medium">-</p>
            </div>
            
            <div className="bg-gray-800/50 p-4 rounded-lg">
              <p className="text-sm text-gray-400">Owner</p>
              <p className="font-medium">-</p>
            </div>
            
            <div className="bg-gray-800/50 p-4 rounded-lg">
              <p className="text-sm text-gray-400">Last Sale Price</p>
              <p className="font-medium">-</p>
            </div>

          </div>
        </div>
      </div>
    </div>
  )
}
