export type DocumentClause = Readonly<{
  clause_id: string
  reference_id: string
  source_hash: string
  ordinal: number
  marker: string
  clause_type: string
  title: string | null
  body: string
  warnings: string[]
}>

export type UploadedDocument = Readonly<{
  document_id: string
  filename: string
  content_type: string | null
  size_bytes: number
  character_count: number
  status: string
  clause_count: number
  clauses: DocumentClause[]
  unclassified_sections: string[]
  document_warnings: string[]
}>
