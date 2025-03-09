"use client"

import Image from 'next/image';
import { useNFTData } from './NftDataContext';

export default function SideInfo() {
  const { nftData, isLoading } = useNFTData();

  if (isLoading) {
    return (
      <div className="w-96 border-l border-gray-700 min-h-full p-6">
        <div className="space-y-6">
          {/* Skeleton Image */}
          <div className="aspect-square w-full bg-gray-800 rounded-lg animate-pulse" />
          
          {/* Skeleton Metadata */}
          <div className="space-y-4">
            <h2 className="w-32 h-7 bg-gray-800 rounded animate-pulse" />
            
            <div className="space-y-2">
              {[1, 2, 3, 4, 5].map((index) => (
                <div key={index} className="bg-gray-800/50 p-4 rounded-lg space-y-2">
                  <div className="w-24 h-4 bg-gray-800 rounded animate-pulse" />
                  <div className="w-full h-5 bg-gray-800 rounded animate-pulse" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="w-96 border-l border-gray-700 min-h-full p-6">
      <div className="space-y-6">
        {/* NFT Image */}
        <div className="aspect-square w-full bg-gray-800 rounded-lg relative">
          {nftData?.imageUrl ? (
            <Image 
              src={nftData.imageUrl} 
              alt="NFT"
              fill
              className="object-contain rounded-lg"
              priority
            />
          ) : (
            <span className="text-gray-400 absolute inset-0 flex items-center justify-center">NFT Image</span>
          )}
        </div>
        
        {/* NFT Metadata */}
        <div className="space-y-4">
          <h2 className="text-xl font-bold">NFT Details</h2>
          
          <div className="space-y-2">
            <div className="bg-gray-800/50 p-4 rounded-lg">
              <p className="text-sm text-gray-400">Collection Name</p>
              <p className="font-medium break-words">{nftData?.collectionName || '-'}</p>
            </div>
                        
            <div className="bg-gray-800/50 p-4 rounded-lg">
              <p className="text-sm text-gray-400">Collection address</p>
              <p className="font-medium break-all">{nftData?.collectionAddress || '-'}</p>
            </div>
            
            <div className="bg-gray-800/50 p-4 rounded-lg">
              <p className="text-sm text-gray-400">Token ID</p>
              <p className="font-medium break-words">{nftData?.tokenId || '-'}</p>
            </div>
            
            <div className="bg-gray-800/50 p-4 rounded-lg">
              <p className="text-sm text-gray-400">Owner</p>
              <p className="font-medium break-all">{nftData?.owner || '-'}</p>
            </div>
            
            <div className="bg-gray-800/50 p-4 rounded-lg">
              <p className="text-sm text-gray-400">Last Sale Price</p>
              <p className="font-medium break-words">{nftData?.lastSalePrice || '-'}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
