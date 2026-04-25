"use client";

import { Download, FileSpreadsheet, FileText } from "lucide-react";

interface Props {
  pdfUrl?: string;
  excelUrl?: string;
}

export default function ExportButtons({ pdfUrl, excelUrl }: Props) {
  return (
    <div className="flex items-center gap-2">
      {pdfUrl && (
        <a href={pdfUrl} target="_blank" rel="noreferrer" className="btn-secondary text-xs">
          <FileText className="w-3.5 h-3.5" />
          PDF
        </a>
      )}
      {excelUrl && (
        <a href={excelUrl} target="_blank" rel="noreferrer" className="btn-secondary text-xs">
          <FileSpreadsheet className="w-3.5 h-3.5" />
          Excel
        </a>
      )}
    </div>
  );
}
