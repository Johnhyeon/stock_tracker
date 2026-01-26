import { useMemo } from 'react'
import MDEditor from '@uiw/react-md-editor'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface MarkdownViewerProps {
  content: string
}

// 상대 경로 이미지를 절대 경로로 변환
function resolveImageUrls(text: string): string {
  // /uploads/... 형태의 상대 경로를 절대 경로로 변환
  return text.replace(
    /(\!\[[^\]]*\]\()(?:\/)(uploads\/[^)]+\))/g,
    `$1${API_URL}/$2`
  )
}

// 이미지 URL 패턴을 마크다운 이미지로 변환
function convertImageUrls(text: string): string {
  // 이미 마크다운 이미지 문법인 경우 제외
  // 순수 URL만 변환 (줄의 시작이나 공백 뒤에 오는 URL)
  const imageUrlPattern = /(?<![(\[])(https?:\/\/[^\s<>]+\.(?:jpg|jpeg|png|gif|webp|bmp|svg)(?:\?[^\s<>]*)?)(?![)\]])/gi

  return text.replace(imageUrlPattern, (url) => {
    return `\n![image](${url})\n`
  })
}

export default function MarkdownViewer({ content }: MarkdownViewerProps) {
  const processedContent = useMemo(() => {
    // 1. 상대 경로를 절대 경로로 변환
    // 2. 순수 이미지 URL을 마크다운으로 변환
    return convertImageUrls(resolveImageUrls(content))
  }, [content])

  return (
    <div data-color-mode="light" className="markdown-viewer">
      <MDEditor.Markdown source={processedContent} />
      <style>{`
        .markdown-viewer img {
          max-width: 100%;
          height: auto;
          border-radius: 8px;
          margin: 16px 0;
        }
        .markdown-viewer p {
          margin-bottom: 12px;
          line-height: 1.7;
        }
        .markdown-viewer h1, .markdown-viewer h2, .markdown-viewer h3 {
          margin-top: 24px;
          margin-bottom: 12px;
          font-weight: 600;
        }
        .markdown-viewer h1 { font-size: 1.5rem; }
        .markdown-viewer h2 { font-size: 1.25rem; }
        .markdown-viewer h3 { font-size: 1.1rem; }
        .markdown-viewer ul, .markdown-viewer ol {
          margin-left: 20px;
          margin-bottom: 12px;
        }
        .markdown-viewer li {
          margin-bottom: 4px;
        }
        .markdown-viewer blockquote {
          border-left: 4px solid #e5e7eb;
          padding-left: 16px;
          color: #6b7280;
          margin: 16px 0;
        }
        .markdown-viewer code {
          background: #f3f4f6;
          padding: 2px 6px;
          border-radius: 4px;
          font-size: 0.9em;
        }
        .markdown-viewer pre {
          background: #f3f4f6;
          padding: 16px;
          border-radius: 8px;
          overflow-x: auto;
          margin: 16px 0;
        }
        .markdown-viewer pre code {
          background: none;
          padding: 0;
        }
      `}</style>
    </div>
  )
}
