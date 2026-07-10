import { useState } from 'react'
import { toast } from 'sonner'
import { analysisApi, type RemixResult } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

/**
 * AI 内容分析面板 (ContentRemixAgent)
 *
 * 流程:选择平台 → 加载已抓取内容 → 选择/输入 note_id → 触发爆款拆解 → 展示报告
 * 需要后端配置 LLM_API_KEY(详见 .env.example)
 */
export function AnalysisPanel() {
  const [platform, setPlatform] = useState('xhs')
  const [platforms, setPlatforms] = useState<string[]>([])
  const [noteId, setNoteId] = useState('')
  const [limit, setLimit] = useState(5)
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<RemixResult[]>([])

  const loadPlatforms = async () => {
    try {
      const res = await analysisApi.getPlatforms()
      setPlatforms(res.data.platforms)
      if (res.data.platforms.length && !res.data.platforms.includes(platform)) {
        setPlatform(res.data.platforms[0])
      }
    } catch (e: any) {
      toast.error('加载平台失败: ' + (e?.message || ''))
    }
  }

  const runRemix = async () => {
    setLoading(true)
    try {
      const req: any = { platform, save: true }
      if (noteId.trim()) {
        req.note_ids = [noteId.trim()]
      } else {
        req.limit = limit
      }
      const res = await analysisApi.remix(req)
      if (!res.data.configured) {
        toast.error('LLM 未配置,请在 .env 设置 LLM_API_KEY')
        return
      }
      setResults(res.data.results)
      toast.success(`分析完成,共 ${res.data.results.length} 条`)
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || ''
      toast.error('分析失败: ' + msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="glass-panel border-cyber-accent/20">
      <CardHeader>
        <CardTitle className="text-cyber-text-primary flex items-center gap-2">
          <span>🤖 内容分析 Agent</span>
          <Button variant="outline" size="sm" onClick={loadPlatforms} disabled={loading}>
            刷新平台
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <Label className="text-cyber-text-secondary">平台</Label>
            <select
              className="bg-cyber-bg border border-cyber-accent/30 rounded px-2 py-1 text-cyber-text-primary"
              value={platform}
              onChange={(e) => setPlatform(e.target.value)}
            >
              {platforms.length === 0 && <option value={platform}>{platform}</option>}
              {platforms.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <Label className="text-cyber-text-secondary">指定 note_id(可选)</Label>
            <Input
              className="w-64"
              value={noteId}
              onChange={(e) => setNoteId(e.target.value)}
              placeholder="留空则批量分析"
            />
          </div>
          {!noteId.trim() && (
            <div className="space-y-1">
              <Label className="text-cyber-text-secondary">批量条数</Label>
              <Input
                type="number"
                min={1}
                max={20}
                className="w-24"
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value) || 5)}
              />
            </div>
          )}
          <Button onClick={runRemix} disabled={loading}>
            {loading ? '分析中...' : '开始拆解'}
          </Button>
        </div>

        <ScrollArea className="h-[420px] rounded border border-cyber-accent/10 p-2">
          {results.length === 0 ? (
            <p className="text-cyber-text-secondary text-sm py-8 text-center">
              选择平台并点击「开始拆解」,生成爆款元素分析报告
            </p>
          ) : (
            <div className="space-y-4">
              {results.map((r, i) => (
                <Card key={i} className="border-cyber-accent/20">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-cyber-text-primary">
                      📌 {r.platform} / {r.note_id}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <pre className="text-xs text-cyber-text-secondary whitespace-pre-wrap font-mono bg-cyber-bg/50 rounded p-2">
                      {r.content_text}
                    </pre>
                    <div className="text-xs text-cyber-text-primary whitespace-pre-wrap leading-relaxed">
                      {r.report}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
