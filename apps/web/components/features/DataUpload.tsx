'use client'

import { useState, useCallback } from 'react'
import { apiClient } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Loader2, Upload, AlertCircle, CheckCircle2, FileSpreadsheet } from 'lucide-react'
import { useResearchDataset } from '@/contexts/ResearchDatasetProvider'
import { buildActiveResearchDataset } from '@/lib/research-dataset'
import type { MappingResponseShape, UploadResponseShape } from '@/types/research-dataset'

export function DataUpload() {
  const { activeDatasetSummary, researchDataMode, activateCustomDataset } = useResearchDataset()
  const [file, setFile] = useState<File | null>(null)
  const [uploadResult, setUploadResult] = useState<UploadResponseShape | null>(null)
  const [mappingResult, setMappingResult] = useState<MappingResponseShape | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const isCustomMode = researchDataMode === 'custom_user_data_mode'
  const selectedFileLabel = file ? file.name : 'No file selected'
  const selectedFileDetail = file ? `${(file.size / 1024).toFixed(1)} KB` : 'CSV, XLS, or XLSX'
  const datasetStateLabel = loading
    ? 'Parsing and mapping uploaded data'
    : isCustomMode
      ? 'Custom dataset active across Research'
      : 'Bordbar reference dataset active'
  const datasetStateDetail = loading
    ? 'The uploaded file is being normalized and mapped to the active research context.'
    : isCustomMode
      ? 'Calibration and simulation are now reading from the uploaded dataset.'
      : 'No upload has been activated yet, so the default Bordbar reference remains active.'

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

  return (
    <div className="grid gap-5">
      <Card>
        <CardHeader>
          <CardTitle>Upload Experimental Data</CardTitle>
          <CardDescription>Upload your own RBC storage experimental data to compare against model predictions. Supports CSV and Excel files with time-series metabolite concentrations (mM). Columns are auto-mapped to the model's ~113 metabolite identifiers.</CardDescription>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Badge variant={researchDataMode === 'custom_user_data_mode' ? 'default' : 'secondary'} className="rounded-full">
              {isCustomMode ? activeDatasetSummary.label : 'Bordbar reference mode'}
            </Badge>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-border/60 bg-background/70 p-3">
              <p className="text-[10px] uppercase tracking-[0.28em] text-muted-foreground">Research dataset</p>
              <p className="mt-2 text-sm font-medium">{activeDatasetSummary.label}</p>
              <p className="mt-1 text-xs text-muted-foreground">{activeDatasetSummary.source === 'custom_upload' ? 'Custom upload source' : 'Default Bordbar fallback'}</p>
            </div>
            <div className="rounded-2xl border border-border/60 bg-background/70 p-3">
              <p className="text-[10px] uppercase tracking-[0.28em] text-muted-foreground">Selected file</p>
              <p className="mt-2 text-sm font-medium">{selectedFileLabel}</p>
              <p className="mt-1 text-xs text-muted-foreground">{selectedFileDetail}</p>
            </div>
            <div className="rounded-2xl border border-border/60 bg-background/70 p-3">
              <p className="text-[10px] uppercase tracking-[0.28em] text-muted-foreground">Activation state</p>
              <p className="mt-2 text-sm font-medium">{datasetStateLabel}</p>
              <p className="mt-1 text-xs text-muted-foreground">{datasetStateDetail}</p>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <label className="flex items-center gap-3 px-4 py-4 rounded-xl border-2 border-dashed border-border hover:border-primary/40 transition-colors cursor-pointer">
            <FileSpreadsheet className="h-5 w-5 text-muted-foreground" />
            <div className="flex-1">
              <p className="text-sm font-medium">{file ? file.name : 'Choose file...'}</p>
              <p className="text-xs text-muted-foreground">{file ? `${(file.size / 1024).toFixed(1)} KB` : 'CSV, XLS, or XLSX'}</p>
            </div>
            <input type="file" accept=".csv,.xls,.xlsx" className="hidden" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          </label>
          <div className="rounded-lg border bg-muted/40 p-3">
            <p className="text-xs font-medium text-muted-foreground mb-1">Expected format</p>
            <pre className="text-[10px] font-mono text-muted-foreground leading-relaxed">{`Time_days, GLC, LAC, ATP, ADP, B23PG\n0.0,       5.0, 2.0, 2.5, 0.8, 4.5\n1.0,       4.5, 2.5, 2.3, 1.0, 4.7`}</pre>
          </div>
        </CardContent>
        <CardFooter className="border-t pt-5">
          <Button onClick={handleUpload} disabled={!file || loading} className="gap-2">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            {loading ? 'Processing...' : 'Upload & Parse'}
          </Button>
        </CardFooter>
      </Card>

      {error && <Card className="border-destructive/40 bg-destructive/5"><CardContent className="flex items-start gap-3 pt-6"><AlertCircle className="h-5 w-5 text-destructive shrink-0" /><p className="text-sm text-destructive">{error}</p></CardContent></Card>}

      {uploadResult && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-600" />{uploadResult.filename}</CardTitle>
            <CardDescription>{uploadResult.n_rows} rows, {uploadResult.metabolites.length} metabolite columns, {uploadResult.time_points.length} time points</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader><TableRow>{uploadResult.columns.map((col) => <TableHead key={col}>{col}</TableHead>)}</TableRow></TableHeader>
              <TableBody>
                {uploadResult.preview.slice(0, 5).map((row, i) => (
                  <TableRow key={i}>{uploadResult.columns.map((col) => <TableCell key={col} className="font-mono text-xs">{typeof row[col] === 'number' ? (row[col] as number).toFixed(3) : String(row[col] ?? '')}</TableCell>)}</TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {mappingResult && (
        <Card>
          <CardHeader>
            <CardTitle>Metabolite Mapping</CardTitle>
            <CardDescription>
              <Badge variant="secondary">{Object.keys(mappingResult.mappings).length} matched</Badge>{' '}
              <Badge variant="outline">{mappingResult.unmapped.length} unmapped</Badge>
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-1.5">
            {Object.entries(mappingResult.mappings).map(([col, match]) => (
              <div key={col} className="flex items-center gap-3 text-sm">
                <span className="font-mono text-xs text-muted-foreground w-28 truncate">{col}</span>
                <span className="text-muted-foreground">→</span>
                <span className="font-mono text-xs font-semibold">{match.metabolite}</span>
                <Badge variant={match.confidence > 0.8 ? 'default' : match.confidence > 0.5 ? 'secondary' : 'destructive'} className="text-[10px]">{(match.confidence * 100).toFixed(0)}%</Badge>
              </div>
            ))}
            {mappingResult.unmapped.map((col) => (
              <div key={col} className="flex items-center gap-3 text-sm opacity-50">
                <span className="font-mono text-xs text-muted-foreground w-28 truncate">{col}</span>
                <span className="text-muted-foreground">→</span>
                <span className="text-xs italic text-muted-foreground">No match</span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
