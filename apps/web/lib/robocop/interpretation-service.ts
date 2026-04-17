import type { SimulationContext, RoBoCopInterpretation } from '@/types/robocop-context'
import {
  getSimulationProvenanceObservations,
  getSimulationProvenanceSummary,
} from './research-provenance'

/**
 * Generate a grounded interpretation of simulation results
 * 
 * For v1, this uses rule-based interpretation.
 * Future versions can upgrade to LLM-based analysis.
 */
export function generateSimulationInterpretation(context: SimulationContext): RoBoCopInterpretation {
  const { parameters, timeRange, metabolites, summary } = context
  
  // Build insights from trends
  const insights: string[] = []
  const keyObservations: string[] = []
  const provenanceSummary = getSimulationProvenanceSummary(context)
  
  if (provenanceSummary) {
    keyObservations.push(...getSimulationProvenanceObservations(context))
  }

  // Time-based insights
  if (timeRange.end > 28) {
    insights.push(`Extended storage simulation (${timeRange.end.toFixed(0)} days) shows long-term metabolic dynamics`)
    keyObservations.push(`Simulated ${timeRange.end.toFixed(0)} days of storage`)
  } else {
    insights.push(`Standard storage window (${timeRange.end.toFixed(0)} days) analyzed`)
    keyObservations.push(`Simulated ${timeRange.end.toFixed(0)} days of storage`)
  }
  
  // pH perturbation insights
  if (parameters.ph_perturbation_type !== 'None') {
    insights.push(`${parameters.ph_perturbation_type} perturbation (${parameters.ph_severity} severity, ${parameters.ph_duration}h duration) affects metabolic trajectories`)
    keyObservations.push(`pH ${parameters.ph_perturbation_type} applied: ${parameters.ph_severity} for ${parameters.ph_duration}h`)
  } else {
    keyObservations.push('No pH perturbation applied')
  }

  // Selection-aware insights
  if (context.selectedMetabolites && context.selectedMetabolites.length > 0) {
    const preview = context.selectedMetabolites.slice(0, 5)
    const remaining = context.selectedMetabolites.length - preview.length
    insights.push(
      `Focused metabolite view: ${preview.join(', ')}${remaining > 0 ? `, and ${remaining} more` : ''}`
    )
    keyObservations.push(`Selected metabolites: ${context.selectedMetabolites.join(', ')}`)
  }

  if (context.customParamsSource === 'provided') {
    insights.push('Simulation used calibrated parameter overrides from the latest calibration run')
    keyObservations.push('Latest optimized ODE parameters were injected into the solver')
  } else if (context.customParamsSource === 'auto_loaded') {
    insights.push('Simulation auto-loaded calibrated parameters from the saved Bordbar calibration set')
    keyObservations.push('Auto-loaded calibrated ODE parameters were used')
  } else if (context.customParamsSource === 'defaults') {
    keyObservations.push('Default Bordbar ODE parameters were used')
  }

  // Trend-based insights
  const trends = summary.notableTrends || []
  const decreasingMetabs = trends.filter(t => t.direction === 'decreasing')
  const increasingMetabs = trends.filter(t => t.direction === 'increasing')
  const stableMetabs = trends.filter(t => t.direction === 'stable')
  
  if (decreasingMetabs.length > 0) {
    const highDecrease = decreasingMetabs.filter(t => t.magnitude === 'high')
    if (highDecrease.length > 0) {
      insights.push(`Critical metabolites showing high depletion: ${highDecrease.map(t => t.metabolite).join(', ')}`)
      keyObservations.push(`High depletion: ${highDecrease.map(t => `${t.metabolite} (${t.magnitude})`).join(', ')}`)
    }
  }
  
  if (increasingMetabs.length > 0) {
    const highIncrease = increasingMetabs.filter(t => t.magnitude === 'high')
    if (highIncrease.length > 0) {
      insights.push(`Metabolites accumulating significantly: ${highIncrease.map(t => t.metabolite).join(', ')}`)
      keyObservations.push(`High accumulation: ${highIncrease.map(t => `${t.metabolite} (${t.magnitude})`).join(', ')}`)
    }
  }
  
  // Energy metabolism focus
  const atpTrend = trends.find(t => t.metabolite === 'ATP')
  const gshTrend = trends.find(t => t.metabolite === 'GSH')
  
  if (atpTrend) {
    if (atpTrend.direction === 'decreasing' && atpTrend.magnitude !== 'low') {
      insights.push('ATP depletion indicates energy stress during storage')
      keyObservations.push(`ATP trend: ${atpTrend.direction} (${atpTrend.magnitude})`)
    }
  }
  
  if (gshTrend) {
    if (gshTrend.direction === 'decreasing' && gshTrend.magnitude !== 'low') {
      insights.push('GSH reduction suggests oxidative stress developing')
      keyObservations.push(`GSH trend: ${gshTrend.direction} (${gshTrend.magnitude})`)
    }
  }
  
  // Solver performance
  if (summary.duration > 5) {
    insights.push(`Computationally intensive simulation (${summary.duration.toFixed(1)}s) may indicate stiff dynamics`)
    keyObservations.push(`Solver ${summary.solver} took ${summary.duration.toFixed(1)}s`)
  }
  
  // Generate recommendations
  const recommendations: string[] = []
  
  if (decreasingMetabs.length > increasingMetabs.length) {
    recommendations.push('Consider supplementation strategies for depleted metabolites')
  }
  
  if (parameters.ph_perturbation_type !== 'None' && decreasingMetabs.length > 3) {
    recommendations.push('pH stress exacerbates metabolic depletion - evaluate buffer capacity')
  }
  
  if (atpTrend?.direction === 'decreasing' && atpTrend.magnitude !== 'low') {
    recommendations.push('Monitor energy preservation strategies for stored RBCs')
  }
  
  if (trends.length === 0 || trends.every(t => t.direction === 'stable')) {
    recommendations.push('System appears stable - consider longer storage or stress conditions to reveal dynamics')
  }
  
  // Build summary
  let summaryText = `${provenanceSummary} Simulation of ${timeRange.end.toFixed(0)}-day RBC storage`
  
  if (parameters.ph_perturbation_type !== 'None') {
    summaryText += ` under ${parameters.ph_severity?.toLowerCase() || 'moderate'} ${parameters.ph_perturbation_type.toLowerCase()}`
  }
  
  summaryText += `. `
  
  if (decreasingMetabs.length > 0) {
    summaryText += `${decreasingMetabs.length} key metabolites decreased, `
  }
  if (increasingMetabs.length > 0) {
    summaryText += `${increasingMetabs.length} increased, `
  }
  if (stableMetabs.length > 0) {
    summaryText += `${stableMetabs.length} remained stable. `
  }
  
  if (atpTrend?.direction === 'decreasing') {
    summaryText += `Energy metabolism shows stress with ATP depletion. `
  }
  
  summaryText += `The ${summary.solver} solver completed in ${summary.duration.toFixed(1)}s.`
  
  // Determine confidence
  let confidence: RoBoCopInterpretation['confidence'] = 'medium'
  
  if (trends.length > 0 && trends.some(t => t.magnitude === 'high')) {
    confidence = 'high'
  } else if (trends.length === 0) {
    confidence = 'low'
  }
  
  return {
    summary: summaryText,
    insights,
    recommendations,
    confidence,
    grounding: {
      dataSource: 'Simulation trajectory analysis',
      keyObservations,
    },
  }
}
