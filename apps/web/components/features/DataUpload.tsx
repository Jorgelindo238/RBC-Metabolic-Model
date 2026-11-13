'use client'

import { useState, useCallback } from 'react'
import Link from 'next/link'
import { apiClient } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Loader2, Upload, AlertCircle, FileSpreadsheet, ArrowRight } from 'lucide-react'
import { useResearchDataset } from '@/contexts/ResearchDatasetProvider'
import { buildActiveResearchDataset } from '@/lib/research-dataset'
import { DRAFT_MISSING_FIELDS } from '@/lib/calibration-journey.mjs'
import { StatusLine } from '@/components/platform/research/StatusLine'
import type { MappingResponseShape, UploadResponseShape } from '@/types/research-dataset'

const STEPS = ['File', 'Describe', 'Check'] as const

export function DataUpload() {
  const { activeDatasetSummary, researchDataMode, activateCustomDataset } = useResearchDataset()
  const [file, setFile] = useState<File | null>(null)
  const [uploadResult, setUploadResult] = useState<UploadResponseShape | null>(null)
  const [mappingResult, setMappingResult] = useState<MappingResponseShape | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleUpload = useCallback(async () => {
    if (!file) return
    setLoading(true); setError(null); setUploadResult(null); setMappingResult(null)
    try {
      const formData = new FormData(); formData.append('file', file)
      const res = await apiClient.post<UploadResponseShape>('/data/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
      setUploadResult(res.data)
      activateCustomDataset(buildActiveResearchDataset(res.data))
      const mapRes = await apiClient.post<MappingResponseShape>('/data/map-metabolites', { columns: res.data.metabolites })
      setMappingResult(mapRes.data)
      activateCustomDataset(buildActiveResearchDataset(res.data, mapRes.data))
    } catch (err: any) { setError(err?.response?.data?.detail || err.message || 'Upload failed') }
    finally { setLoading(false) }
  }, [activateCustomDataset, file])

  const uploaded = researchDataMode === 'custom_user_data_mode'
  // Steps are a status, not navigation: nothing after "File" exists until a file is imported.
  const step = uploadResult || uploaded ? 1 : 0

  return <div className="grid gap-6" data-testid="research-data-upload">
    <ol className="r-toolbar text-[13px]" aria-label="Import steps">
      {STEPS.map((name, i) => <li key={name} aria-current={i === step ? 'step' : undefined}
        className={i <= step ? '' : 'research-muted'}>{i + 1} {name}</li>)}
    </ol>

    <section id="dataset-intake" className="research-section" aria-label="File and preview">
      <div className="research-toolbar">
        <label className="research-file-input">
          <FileSpreadsheet size={19} aria-hidden="true" />
          <strong>{file?.name ?? 'Choose file'}</strong>
          <span className="research-muted">{file ? `${(file.size / 1024).toFixed(1)} KB` : 'CSV / XLS / XLSX'}</span>
          <input type="file" aria-label="Experimental data file" accept=".csv,.xls,.xlsx" disabled={loading}
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null)
              setUploadResult(null)
              setMappingResult(null)
              setError(null)
            }} />
        </label>
        <Button onClick={handleUpload} disabled={!file || loading} className="gap-2">
          {loading ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
          {loading ? 'Processing...' : 'Upload & parse'}
        </Button>
      </div>
      {error ? <p role="alert" className="mt-4 flex items-start gap-2 text-sm text-destructive"><AlertCircle size={16} className="shrink-0" />{error}</p> : null}
      {loading && !uploadResult ? <p className="research-empty" role="status">Reading file...</p> : null}
      {uploadResult ? <div className="research-preview">
        <h2>Preview</h2>
        <p className="mb-3 text-xs text-muted-foreground">{uploadResult.filename} / {uploadResult.n_rows} rows / {uploadResult.time_points.length} dates. Values are shown exactly as read.</p>
        <Table>
          <TableHeader><TableRow>{uploadResult.columns.map((col) => <TableHead key={col}>{col}</TableHead>)}</TableRow></TableHeader>
          <TableBody>{uploadResult.preview.slice(0, 5).map((row, i) => (
            <TableRow key={i}>{uploadResult.columns.map((col) => <TableCell key={col} className="font-mono text-xs">{String(row[col] ?? '')}</TableCell>)}</TableRow>
          ))}</TableBody>
        </Table>
      </div> : null}
    </section>

    {mappingResult || (loading && uploadResult) ? <section id="validation-alignment" className="research-section">
      <div className="research-section-heading"><h2>Metabolite mapping</h2>
        {mappingResult ? <span className="research-muted">{Object.keys(mappingResult.mappings).length} matched / {mappingResult.unmapped.length} unmatched</span> : null}
      </div>
      {mappingResult ? <div className="overflow-x-auto"><Table>
        <TableHeader><TableRow><TableHead>Source column</TableHead><TableHead>Model metabolite</TableHead><TableHead>Name match</TableHead></TableRow></TableHeader>
        <TableBody>
          {Object.entries(mappingResult.mappings).map(([col, match]) => <TableRow key={col}>
            <TableCell className="font-mono text-xs">{col}</TableCell><TableCell className="font-mono text-xs">{match.metabolite}</TableCell>
            <TableCell>{(match.confidence * 100).toFixed(0)}%</TableCell>
          </TableRow>)}
          {mappingResult.unmapped.map((col) => <TableRow key={col}><TableCell className="font-mono text-xs">{col}</TableCell><TableCell>Unmatched</TableCell><TableCell>-</TableCell></TableRow>)}
        </TableBody>
      </Table></div> : <p className="research-empty" role="status">Mapping pending...</p>}
    </section> : null}

    {uploaded ? <section id="data-readiness" className="research-section">
      <div className="research-section-heading"><h2>Describe and check</h2>
        <Link className="research-text-link inline-flex items-center gap-2" href="/research/parameter-calibration">Calibration <ArrowRight size={14} /></Link></div>
      <div className="grid gap-2">
        <StatusLine tone="ok" label="Active dataset" value={activeDatasetSummary.label} />
        <StatusLine label="Contract" value="Not checked" detail="Check it on the Calibration page; nothing is launched." />
        <StatusLine tone="warn" label="Not provided by the file" value={`${DRAFT_MISSING_FIELDS.length} fields`}
          detail="They stay missing: nothing is prefilled, no reference initial state is borrowed, relative values are never converted to mM." />
      </div>
      <ul className="mt-3 list-disc pl-5 text-[13px] research-muted" data-testid="upload-missing-fields">
        {DRAFT_MISSING_FIELDS.map((field) => <li key={field}>{field}</li>)}
      </ul>
    </section> : null}
  </div>
}
