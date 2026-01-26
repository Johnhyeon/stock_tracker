import { useCallback, useRef } from 'react'
import MDEditor, { commands } from '@uiw/react-md-editor'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface MarkdownEditorProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  minHeight?: number
}

export default function MarkdownEditor({
  value,
  onChange,
  placeholder = '투자 논리를 작성하세요...\n\n이미지는 드래그앤드롭 또는 붙여넣기로 추가할 수 있습니다.',
  minHeight = 300,
}: MarkdownEditorProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)

  const uploadImage = async (file: File): Promise<string | null> => {
    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch(`${API_URL}/api/v1/uploads`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const error = await response.json()
        alert(error.detail || '업로드 실패')
        return null
      }

      const data = await response.json()
      // 상대 경로만 반환 (환경 독립적)
      return data.url
    } catch (err) {
      console.error('Upload error:', err)
      alert('이미지 업로드에 실패했습니다.')
      return null
    }
  }

  const insertImageMarkdown = (url: string, filename: string) => {
    const imageMarkdown = `![${filename}](${url})`
    onChange(value ? `${value}\n\n${imageMarkdown}` : imageMarkdown)
  }

  const handlePaste = useCallback(
    async (event: React.ClipboardEvent) => {
      const items = event.clipboardData?.items
      if (!items) return

      for (const item of items) {
        if (item.type.startsWith('image/')) {
          event.preventDefault()
          const file = item.getAsFile()
          if (file) {
            const url = await uploadImage(file)
            if (url) {
              insertImageMarkdown(url, 'pasted-image')
            }
          }
          return
        }
      }
    },
    [value, onChange]
  )

  const handleDrop = useCallback(
    async (event: React.DragEvent) => {
      const files = event.dataTransfer?.files
      if (!files || files.length === 0) return

      for (const file of files) {
        if (file.type.startsWith('image/')) {
          event.preventDefault()
          const url = await uploadImage(file)
          if (url) {
            insertImageMarkdown(url, file.name)
          }
        }
      }
    },
    [value, onChange]
  )

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (!files) return

    for (const file of files) {
      const url = await uploadImage(file)
      if (url) {
        insertImageMarkdown(url, file.name)
      }
    }

    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const imageCommand: commands.ICommand = {
    name: 'image',
    keyCommand: 'image',
    buttonProps: { 'aria-label': 'Insert image' },
    icon: (
      <svg width="12" height="12" viewBox="0 0 20 20">
        <path
          fill="currentColor"
          d="M15 9c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm4-7H1c-.55 0-1 .45-1 1v14c0 .55.45 1 1 1h18c.55 0 1-.45 1-1V3c0-.55-.45-1-1-1zm-1 13l-6-5-2 2-4-5-4 8V4h16v11z"
        />
      </svg>
    ),
    execute: () => {
      fileInputRef.current?.click()
    },
  }

  return (
    <div
      data-color-mode="light"
      onPaste={handlePaste}
      onDrop={handleDrop}
      onDragOver={(e) => e.preventDefault()}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        multiple
        onChange={handleFileSelect}
        style={{ display: 'none' }}
      />
      <MDEditor
        value={value}
        onChange={(val) => onChange(val || '')}
        preview="edit"
        height={minHeight}
        textareaProps={{
          placeholder,
        }}
        commands={[
          commands.bold,
          commands.italic,
          commands.strikethrough,
          commands.hr,
          commands.divider,
          commands.link,
          imageCommand,
          commands.divider,
          commands.unorderedListCommand,
          commands.orderedListCommand,
          commands.checkedListCommand,
          commands.divider,
          commands.codeBlock,
          commands.quote,
        ]}
      />
      <p className="text-xs text-gray-500 mt-1">
        이미지: 드래그앤드롭, 붙여넣기(Ctrl+V), 또는 툴바의 이미지 버튼 사용
      </p>
    </div>
  )
}
