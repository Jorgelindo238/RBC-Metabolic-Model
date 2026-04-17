import { NextRequest, NextResponse } from 'next/server'

export const runtime = 'nodejs'

const SCIENCE_DEFAULT_BASE_URL = 'https://api.airbc.org/api'
const MONITORING_DEFAULT_BASE_URL = 'https://monitoring-api.airbc.org/api'
const RESEARCH_DEFAULT_BASE_URL = 'https://research-api.airbc.org/api'

const HOP_BY_HOP_HEADERS = new Set([
  'connection',
  'content-encoding',
  'content-length',
  'host',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
])

function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, '')
}

function resolveBaseUrl(path: string[]) {
  const [segment] = path

  if (segment === 'monitoring') {
    return trimTrailingSlash(
      process.env.MONITORING_API_BASE_URL ??
        process.env.NEXT_PUBLIC_MONITORING_API_BASE_URL ??
        MONITORING_DEFAULT_BASE_URL
    )
  }

  if (segment === 'robocop') {
    return trimTrailingSlash(
      process.env.RESEARCH_API_BASE_URL ??
        process.env.NEXT_PUBLIC_RESEARCH_API_BASE_URL ??
        RESEARCH_DEFAULT_BASE_URL
    )
  }

  if (segment === 'calibration') {
    const calibrationBaseUrl =
      process.env.CALIBRATION_API_BASE_URL ?? process.env.NEXT_PUBLIC_CALIBRATION_API_BASE_URL

    return calibrationBaseUrl ? trimTrailingSlash(calibrationBaseUrl) : null
  }

  return trimTrailingSlash(
    process.env.SCIENCE_API_BASE_URL ??
      process.env.NEXT_PUBLIC_API_URL ??
      SCIENCE_DEFAULT_BASE_URL
  )
}

function buildUpstreamUrl(request: NextRequest, path: string[]) {
  const baseUrl = resolveBaseUrl(path)
  if (!baseUrl) {
    return null
  }

  const joinedPath = path.join('/')
  const upstream = new URL(`${baseUrl}/${joinedPath}`)
  upstream.search = request.nextUrl.search
  return upstream
}

function buildHeaders(request: NextRequest) {
  const headers = new Headers(request.headers)

  for (const header of HOP_BY_HOP_HEADERS) {
    headers.delete(header)
  }

  return headers
}

async function proxyRequest(request: NextRequest, path: string[]) {
  const upstream = buildUpstreamUrl(request, path)

  if (!upstream) {
    return NextResponse.json(
      {
        detail:
          'Calibration worker is not configured yet. Set CALIBRATION_API_BASE_URL on the web deployment.',
      },
      { status: 503 }
    )
  }

  const init: RequestInit = {
    method: request.method,
    headers: buildHeaders(request),
    redirect: 'manual',
  }

  if (request.method !== 'GET' && request.method !== 'HEAD') {
    const body = await request.arrayBuffer()
    init.body = body.byteLength > 0 ? body : undefined
  }

  const upstreamResponse = await fetch(upstream, init)
  const responseHeaders = new Headers(upstreamResponse.headers)

  for (const header of HOP_BY_HOP_HEADERS) {
    responseHeaders.delete(header)
  }

  return new NextResponse(upstreamResponse.body, {
    headers: responseHeaders,
    status: upstreamResponse.status,
    statusText: upstreamResponse.statusText,
  })
}

type RouteContext = {
  params: Promise<{ path: string[] }>
}

async function resolvePath(context: RouteContext) {
  const params = await context.params
  return Array.isArray(params.path) ? params.path : []
}

export async function GET(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, await resolvePath(context))
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, await resolvePath(context))
}

export async function PUT(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, await resolvePath(context))
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, await resolvePath(context))
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, await resolvePath(context))
}

export async function OPTIONS(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, await resolvePath(context))
}
