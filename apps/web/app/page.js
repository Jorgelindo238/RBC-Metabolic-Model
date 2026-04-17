import { PlatformFeaturePage } from '../components/platform/PlatformFeaturePage.tsx'

function normalizeSearchParam(value) {
  return Array.isArray(value) ? value[0] : value
}

export default async function Page({ searchParams }) {
  const resolvedSearchParams = (await searchParams) ?? {}
  const selectedFeatureId = normalizeSearchParam(resolvedSearchParams.feature) ?? 'home'
  const selectedSubsectionId = normalizeSearchParam(resolvedSearchParams.subsection) ?? null
  return <PlatformFeaturePage featureId={selectedFeatureId} subsectionId={selectedSubsectionId} />
}
