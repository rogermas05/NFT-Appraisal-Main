"use client"

import { Search, SwitchCamera, X } from "lucide-react"
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

  const clearInputs = () => {
    setNftLink("")
    setContractAddress("")
    setTokenId("")
  }

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
    <header className="w-full bg-bgcol p-3 border-b border-gray-700">
      <div className="relative px-4">
        <div className="text-3xl font-extrabold absolute left-4 bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 text-transparent bg-clip-text tracking-tight cursor-pointer transition-transform duration-200 hover:opacity-90">
          NFT Appraiser
        </div>
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
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={clearInputs}
                    className="absolute right-2 top-1/2 -translate-y-1/2 z-10 hover:bg-transparent hover:opacity-70"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                  <Input
                    type="url"
                    placeholder="Enter NFT link..."
                    className="pl-10 pr-10 w-full"
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
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={clearInputs}
                    className="absolute right-1 top-1/2 -translate-y-1/2 z-10 hover:bg-transparent"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                  <Input
                    type="text"
                    placeholder="Contract Address"
                    className="pr-10"
                    value={contractAddress}
                    onChange={(e) => setContractAddress(e.target.value)}
                  />
                </div>
                <div className="relative flex-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={clearInputs}
                    className="absolute right-1 top-1/2 -translate-y-1/2 z-10 hover:bg-transparent"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                  <Input
                    type="text"
                    placeholder="Token ID"
                    className="pr-10"
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
      </div>
    </header>
  )
}
