import { useCallback, useRef, useState } from 'react'

interface Options { multiple?: boolean; accept?: string[] }

export interface FileDropZone {
  arquivos: File[]; dragOver: boolean; inputRef: React.RefObject<HTMLInputElement>
  addFiles(f: File[]): void; removeFile(i: number): void; clearFiles(): void
  onDrop(e: React.DragEvent): void; onDragOver(e: React.DragEvent): void
  onDragLeave(e: React.DragEvent): void; onInputChange(e: React.ChangeEvent<HTMLInputElement>): void
}

export function useFileDropZone({ multiple = true, accept }: Options = {}): FileDropZone {
  const [arquivos, setArquivos] = useState<File[]>([])
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const addFiles = useCallback((files: File[]) => {
    const valid = accept ? files.filter(f => accept.some(e => f.name.toLowerCase().endsWith(e))) : files
    setArquivos(prev => multiple ? [...prev, ...valid] : valid.slice(0, 1))
  }, [accept, multiple])
  const removeFile = useCallback((i: number) => setArquivos(prev => prev.filter((_, idx) => idx !== i)), [])
  const clearFiles = useCallback(() => setArquivos([]), [])
  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false); addFiles(Array.from(e.dataTransfer.files))
  }, [addFiles])
  const onDragOver = useCallback((e: React.DragEvent) => { e.preventDefault(); setDragOver(true) }, [])
  const onDragLeave = useCallback((e: React.DragEvent) => {
    if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragOver(false)
  }, [])
  const onInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) addFiles(Array.from(e.target.files))
  }, [addFiles])
  return { arquivos, dragOver, inputRef, addFiles, removeFile, clearFiles, onDrop, onDragOver, onDragLeave, onInputChange }
}
