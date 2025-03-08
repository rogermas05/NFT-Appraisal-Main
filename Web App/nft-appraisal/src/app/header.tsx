"use client"

import { Search, SwitchCamera } from "lucide-react"
import { useState } from "react"
import { Button } from "../components/ui/button"
import { Input } from "../components/ui/input"
import { useNFTData } from './NftDataContext'

function convertIpfsUrl(url: string): string {
  if (url.startsWith('ipfs://')) {
    return url.replace('ipfs://', 'https://ipfs.io/ipfs/')
  }
  return url
}

export default function Header() {
  const [isManualInput, setIsManualInput] = useState(false)
  const [nftLink, setNftLink] = useState("")
  const [contractAddress, setContractAddress] = useState("")
  const [tokenId, setTokenId] = useState("")
  const { setNftData, setIsLoading } = useNFTData()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    
    try {
      let finalContractAddress = contractAddress
      let finalTokenId = tokenId

      if (!isManualInput && nftLink) {
        // Parse OpenSea URL
        const openseaRegex = /opensea\.io\/item\/ethereum\/([^\/]+)\/(\d+)/
        const match = nftLink.match(openseaRegex)
        
        if (match) {
          finalContractAddress = match[1]
          finalTokenId = match[2]
        } else {
          throw new Error('Invalid OpenSea URL format')
        }
      }

      const response = await fetch(
        `https://get-nft-data-dkwdhhyv7q-uc.a.run.app/?contract_address=${finalContractAddress}&token_id=${finalTokenId}`
      )

      if (!response.ok) {
        throw new Error('Failed to fetch NFT data')
      }

      const data = await response.json()
      const lastSale = data.sales_history && data.sales_history.length > 0 
        ? data.sales_history[0] 
        : null

      setNftData({
        collectionName: data.name || '-',
        collectionAddress: data.token_address || '-',
        tokenId: data.token_id || '-',
        owner: data.owner || '-',
        lastSalePrice: lastSale 
          ? `${lastSale.price_ethereum} ETH ($${lastSale.price_usd.toFixed(2)})` 
          : '-',
        imageUrl: data.image ? convertIpfsUrl(data.image) : undefined
      })
    } catch (error) {
      console.error('Error fetching NFT data:', error)
      setNftData(null)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <header className="w-full bg-bgcol p-4 pt-6 border-b border-gray-700">
      <form onSubmit={handleSubmit} className="w-full max-w-lg mx-auto">
        <div className="relative flex gap-2">
          <div className="flex-1 flex gap-2 overflow-hidden relative">
            <div 
              className={`absolute inset-0 flex gap-2 w-full transition-all duration-500 ease-in-out ${
                isManualInput ? 'translate-x-full opacity-0' : 'translate-x-0 opacity-100'
              }`}
            >
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type="url"
                  placeholder="Enter NFT link..."
                  className="pl-10 w-full"
                  value={nftLink}
                  onChange={(e) => setNftLink(e.target.value)}
                />
                <button type="submit" className="sr-only">
                  Search
                </button>
              </div>
            </div>

            <div 
              className={`absolute inset-0 flex gap-2 w-full transition-all duration-500 ease-in-out ${
                isManualInput ? 'translate-x-0 opacity-100' : '-translate-x-full opacity-0'
              }`}
            >
              <div className="relative flex-1">
                <Input
                  type="text"
                  placeholder="Contract Address"
                  value={contractAddress}
                  onChange={(e) => setContractAddress(e.target.value)}
                />
              </div>
              <div className="relative flex-1">
                <Input
                  type="text"
                  placeholder="Token ID"
                  value={tokenId}
                  onChange={(e) => setTokenId(e.target.value)}
                />
              </div>
              <button type="submit" className="sr-only">
                Search
              </button>
            </div>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() => setIsManualInput(!isManualInput)}
            className="shrink-0"
          >
            <SwitchCamera className="h-4 w-4" />
          </Button>
        </div>
      </form>
    </header>
  )
}
