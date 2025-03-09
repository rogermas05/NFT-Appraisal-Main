import { createContext, ReactNode, useContext, useState } from 'react';

interface NFTData {
  collectionName: string;
  collectionAddress: string;
  tokenId: string;
  owner: string;
  lastSalePrice: string;
  imageUrl?: string;
  appraisalData?: {
    price: number;
    text: string;
    standard_deviation: number;
    total_confidence: number;
    ethereum_price_usd: number;
  };
}

interface NFTDataContextType {
  nftData: NFTData | null;
  setNftData: (data: NFTData | null) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  isAppraisalLoading: boolean;
  setIsAppraisalLoading: (loading: boolean) => void;
  selectedModels: string[];
  setSelectedModels: (models: string[]) => void;
}

const NFTDataContext = createContext<NFTDataContextType | undefined>(undefined);

export function NFTDataProvider({ children }: { children: ReactNode }) {
  const [nftData, setNftData] = useState<NFTData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isAppraisalLoading, setIsAppraisalLoading] = useState(false);
  const [selectedModels, setSelectedModels] = useState<string[]>(["regression", "confidence"]);

  return (
    <NFTDataContext.Provider value={{ 
      nftData, 
      setNftData, 
      isLoading, 
      setIsLoading,
      isAppraisalLoading,
      setIsAppraisalLoading,
      selectedModels,
      setSelectedModels
    }}>
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