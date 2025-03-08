import { createContext, ReactNode, useContext, useState } from 'react';

interface NFTData {
  collectionName: string;
  collectionAddress: string;
  tokenId: string;
  owner: string;
  lastSalePrice: string;
  imageUrl?: string;
}

interface NFTDataContextType {
  nftData: NFTData | null;
  setNftData: (data: NFTData | null) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
}

const NFTDataContext = createContext<NFTDataContextType | undefined>(undefined);

export function NFTDataProvider({ children }: { children: ReactNode }) {
  const [nftData, setNftData] = useState<NFTData | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  return (
    <NFTDataContext.Provider value={{ nftData, setNftData, isLoading, setIsLoading }}>
      {children}
    </NFTDataContext.Provider>
  );
}

export function useNFTData() {
  const context = useContext(NFTDataContext);
  if (context === undefined) {
    throw new Error('useNFTData must be used within a NFTDataProvider');
  }
  return context;
} 