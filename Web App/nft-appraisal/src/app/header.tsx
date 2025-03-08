"use client"

import { Search, SwitchCamera } from "lucide-react"
import { useState } from "react"
import { Button } from "../components/ui/button"
import { Input } from "../components/ui/input"

export default function Header() {
  const [isManualInput, setIsManualInput] = useState(false)
  const [nftLink, setNftLink] = useState("")
  const [contractAddress, setContractAddress] = useState("")
  const [tokenId, setTokenId] = useState("")

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (isManualInput) {
      console.log("Submitted contract:", contractAddress, "token:", tokenId)
    } else {
      console.log("Submitted NFT link:", nftLink)
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
