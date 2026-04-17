'use client'

import { useState, useCallback } from 'react'
import { apiClient } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Progress } from '@/components/ui/progress'
import { Loader2, BarChart3, AlertCircle, Info } from 'lucide-react'

interface SensitivityResult {
  metabolite_comparison: { Metabolite: string; Bordbar_Mean: number; Custom_Mean: number; RMSE: number; Percent_Change: number }[]
  top_sensitive_metabolites: { name: string; pct_change: number }[]
  validation_metrics: Record<string, { R2: number; RMSE: number; MAE: number; n_points: number }>
  simulation_summary: { success: boolean; n_metabolites: number; duration: number }
}

export function SensitivityAnalysis() {
  const [result, setResult] = useState<SensitivityResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const runDemo = useCallback(async () => {
    setLoading(true); setError(null); setResult(null)
    try {
      const expRes = await apiClient.get('/data/experimental')
      const { metabolites, time_points, values } = expRes.data
      const noisyValues = (values as number[][]).map((row: number[]) => row.map((v: number) => v * (1 + (Math.random() - 0.5) * 0.15)))
      const res = await apiClient.post<SensitivityResult>('/sensitivity/compare', { custom_time: time_points, custom_metabolites: metabolites, custom_values: noisyValues, t_max: 42 })
      setResult(res.data)
    } catch (err: any) { setError(err?.response?.data?.detail || err.message || 'Analysis failed') }
    finally { setLoading(false) }
  }, [])

  return (
    <div className="grid gap-5">
      <Card>
        <CardHeader>
          <CardTitle>Sensitivity Analysis</CardTitle>
          <CardDescription>Compare how well the mechanistic model reproduces different experimental datasets. Since the ODE system is governed by fixed kinetic laws, this analysis compares your measurements against the Bordbar et al. reference to identify metabolites with the largest discrepancies.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-lg border bg-muted/40 p-3 mb-4 flex items-start gap-2">
            <Info className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
            <p className="text-xs text-muted-foreground leading-relaxed">The RBC model uses fixed kinetic laws, so this analysis compares <strong>your measurements vs Bordbar et al.</strong> to identify metabolites with the biggest discrepancies.</p>
          </div>
        </CardContent>
        <CardFooter className="border-t pt-5">
          <Button onClick={runDemo} disabled={loading} className="gap-2">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <BarChart3 className="h-4 w-4" />}
            {loading ? 'Analysing...' : 'Run Comparative Analysis (demo)'}
          </Button>
        </CardFooter>
      </Card>

      {error && (
        <Card className="border-destructive/40 bg-destructive/5">
          <CardContent className="flex items-start gap-3 pt-6"><AlertCircle className="h-5 w-5 text-destructive shrink-0" /><p className="text-sm text-destructive">{error}</p></CardContent>
        </Card>
      )}

      {result?.top_sensitive_metabolites.length ? (
        <Card>
          <CardHeader><CardTitle>Top Sensitive Metabolites</CardTitle><CardDescription>Largest differences between datasets.</CardDescription></CardHeader>
          <CardContent className="space-y-2">
            {result.top_sensitive_metabolites.slice(0, 10).map((m) => (
              <div key={m.name} className="flex items-center gap-3">
                <Badge variant="outline" className="font-mono w-16 justify-center text-[11px]">{m.name}</Badge>
                <Progress value={Math.min(Math.abs(m.pct_change), 100)} className="flex-1 h-2" />
                <span className={`w-16 text-right font-mono text-xs ${m.pct_change > 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                  {m.pct_change > 0 ? '+' : ''}{m.pct_change.toFixed(1)}%
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {result && Object.keys(result.validation_metrics).length > 0 && (
        <Card>
          <CardHeader><CardTitle>Validation Metrics</CardTitle><CardDescription>Model fit quality per metabolite.</CardDescription></CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Metabolite</TableHead>
                  <TableHead className="text-right">R²</TableHead>
                  <TableHead className="text-right">RMSE</TableHead>
                  <TableHead className="text-right">MAE</TableHead>
                  <TableHead className="text-right">Pts</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Object.entries(result.validation_metrics).sort(([, a], [, b]) => b.R2 - a.R2).slice(0, 20).map(([name, m]) => (
                  <TableRow key={name}>
                    <TableCell className="font-mono font-medium">{name}</TableCell>
                    <TableCell className={`text-right font-mono ${m.R2 > 0.9 ? 'text-emerald-600' : m.R2 > 0.5 ? 'text-amber-600' : 'text-red-500'}`}>{m.R2.toFixed(3)}</TableCell>
                    <TableCell className="text-right font-mono text-muted-foreground">{m.RMSE.toFixed(4)}</TableCell>
                    <TableCell className="text-right font-mono text-muted-foreground">{m.MAE.toFixed(4)}</TableCell>
                    <TableCell className="text-right text-muted-foreground">{m.n_points}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
