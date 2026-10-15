import { useMemo } from 'react'
import { useReview, type IconId } from '../store'
import { glyphSvg, iconSvg } from './concepts'

/** The app icon as it appears inside the product (title bar, sidebar, About, notifications). */
export function AppMark({ size = 20, id }: { size?: number; id?: IconId }) {
  const current = useReview((r) => r.icon)
  const icon = id ?? current
  const html = useMemo(() => iconSvg(icon, size), [icon, size])
  return <span aria-hidden className="inline-flex shrink-0" style={{ width: size, height: size }} dangerouslySetInnerHTML={{ __html: html }} />
}

export function Glyph({ id, size = 16, color }: { id: IconId; size?: number; color?: string }) {
  const html = useMemo(() => glyphSvg(id, size, color), [id, size, color])
  return <span aria-hidden className="inline-flex shrink-0" style={{ width: size, height: size, color }} dangerouslySetInnerHTML={{ __html: html }} />
}
