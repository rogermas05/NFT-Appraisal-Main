"use client"

import Header from "./header"
import ModelComparison from "./modelcomparison"
import { NFTDataProvider } from './NftDataContext'
import SideInfo from "./sideinfo"

export default function HomePage() {
  return (
    <NFTDataProvider>
      <main className="flex min-h-screen flex-col bg-bgcol text-white">
        <Header />
        <div className="flex flex-1">
          <ModelComparison />
          <SideInfo />
        </div>
      </main>
    </NFTDataProvider>
  )
}
