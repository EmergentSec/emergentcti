import { useState, useCallback, useRef, type DragEvent } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import { useCSVPreview, useImportCSV, useImportSTIX } from '@/hooks/useExport';
import { useToast } from '@/contexts/ToastContext';
import type { CSVPreviewResponse, CSVImportResponse, STIXImportResponse } from '@/types/export';

type FileFormat = 'csv' | 'stix';
type Step = 1 | 2 | 3 | 4;

const COLUMN_OPTIONS = [
  { value: '', label: '-- Skip --' },
  { value: 'type', label: 'Type' },
  { value: 'value', label: 'Value' },
  { value: 'tlp', label: 'TLP' },
  { value: 'confidence_score', label: 'Confidence Score' },
  { value: 'tags', label: 'Tags' },
  { value: 'category', label: 'Category' },
  { value: 'description', label: 'Description' },
  { value: 'first_seen', label: 'First Seen' },
  { value: 'last_seen', label: 'Last Seen' },
];

export function ImportPage() {
  const [step, setStep] = useState<Step>(1);
  const [file, setFile] = useState<File | null>(null);
  const [format, setFormat] = useState<FileFormat | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [preview, setPreview] = useState<CSVPreviewResponse | null>(null);
  const [columnMapping, setColumnMapping] = useState<Record<string, string>>({});
  const [results, setResults] = useState<CSVImportResponse | STIXImportResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const csvPreviewMutation = useCSVPreview();
  const importCSVMutation = useImportCSV();
  const importSTIXMutation = useImportSTIX();
  const { addToast } = useToast();

  const detectFormat = (f: File): FileFormat | null => {
    const name = f.name.toLowerCase();
    if (name.endsWith('.csv')) return 'csv';
    if (name.endsWith('.json') || name.endsWith('.stix')) return 'stix';
    return null;
  };

  const handleFile = useCallback((f: File) => {
    const detected = detectFormat(f);
    if (!detected) {
      addToast('Unsupported file format. Please upload a CSV or STIX JSON file.', 'error');
      return;
    }
    setFile(f);
    setFormat(detected);
    setPreview(null);
    setColumnMapping({});
    setResults(null);

    if (detected === 'csv') {
      // Auto-preview CSV
      csvPreviewMutation.mutate(
        { file: f },
        {
          onSuccess: (data) => {
            setPreview(data);
            setColumnMapping(data.detected_mapping);
            setStep(2);
          },
          onError: () => {
            addToast('Failed to preview CSV file', 'error');
          },
        }
      );
    } else {
      // STIX goes directly to confirm step
      setStep(3);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      handleFile(droppedFile);
    }
  };

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => {
    setDragOver(false);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      handleFile(selected);
    }
  };

  const handleMappingChange = (csvColumn: string, targetField: string) => {
    setColumnMapping((prev) => {
      const next = { ...prev };
      if (targetField) {
        next[csvColumn] = targetField;
      } else {
        delete next[csvColumn];
      }
      return next;
    });
  };

  const handleConfirmImport = () => {
    if (!file) return;

    if (format === 'csv') {
      importCSVMutation.mutate(
        { file, columnMapping },
        {
          onSuccess: (data) => {
            setResults(data);
            setStep(4);
            addToast(`Imported ${data.imported} observables`, 'success');
          },
          onError: () => {
            addToast('CSV import failed', 'error');
          },
        }
      );
    } else {
      importSTIXMutation.mutate(file, {
        onSuccess: (data) => {
          setResults(data);
          setStep(4);
          addToast(`Imported ${data.imported} observables`, 'success');
        },
        onError: () => {
          addToast('STIX import failed', 'error');
        },
      });
    }
  };

  const handleReset = () => {
    setStep(1);
    setFile(null);
    setFormat(null);
    setPreview(null);
    setColumnMapping({});
    setResults(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const isImporting = importCSVMutation.isPending || importSTIXMutation.isPending;

  const mappedFieldCount = Object.values(columnMapping).filter(Boolean).length;
  const hasValueMapping = Object.values(columnMapping).includes('value');

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Import Observables</h1>
        <p className="text-muted-foreground">
          Import observables from CSV or STIX 2.1 JSON files
        </p>
      </div>

      {/* Step Indicator */}
      <div className="flex items-center gap-2">
        {[1, 2, 3, 4].map((s) => (
          <div key={s} className="flex items-center gap-2">
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                step === s
                  ? 'bg-primary text-primary-foreground'
                  : step > s
                    ? 'bg-primary/20 text-primary'
                    : 'bg-muted text-muted-foreground'
              }`}
            >
              {step > s ? '\u2713' : s}
            </div>
            <span
              className={`text-sm ${
                step === s ? 'font-medium text-foreground' : 'text-muted-foreground'
              }`}
            >
              {s === 1
                ? 'Upload'
                : s === 2
                  ? 'Map Columns'
                  : s === 3
                    ? 'Confirm'
                    : 'Results'}
            </span>
            {s < 4 && (
              <div className="mx-2 h-px w-8 bg-border" />
            )}
          </div>
        ))}
      </div>

      {/* Step 1: File Upload */}
      {step === 1 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Upload File</CardTitle>
            <CardDescription>
              Drag and drop a file or click to browse. Supported formats: CSV, STIX 2.1 JSON.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => fileInputRef.current?.click()}
              className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-12 transition-colors ${
                dragOver
                  ? 'border-primary bg-primary/5'
                  : 'border-border hover:border-primary/50 hover:bg-muted/50'
              }`}
            >
              <div className="text-4xl mb-4">{'\u21EA'}</div>
              <p className="text-sm font-medium">
                Drop your file here, or click to browse
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                CSV (.csv) or STIX 2.1 JSON (.json)
              </p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.json,.stix"
                onChange={handleFileInput}
                className="hidden"
              />
            </div>
            {csvPreviewMutation.isPending && (
              <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                Analyzing file...
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Step 2: Column Mapping (CSV only) */}
      {step === 2 && preview && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Column Mapping</CardTitle>
            <CardDescription>
              Map CSV columns to observable fields. {preview.total_rows} rows detected.
              {preview.errors.length > 0 && (
                <span className="text-amber-400">
                  {' '}{preview.errors.length} warning(s) found.
                </span>
              )}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Mapping Controls */}
            <div className="space-y-3">
              <p className="text-sm font-medium">Field Mapping</p>
              <div className="grid gap-3">
                {Object.keys(preview.rows[0] || {}).map((csvCol) => (
                  <div
                    key={csvCol}
                    className="flex items-center gap-3 rounded-md border border-border p-3"
                  >
                    <span className="w-40 truncate text-sm font-mono font-medium">
                      {csvCol}
                    </span>
                    <span className="text-muted-foreground">{'\u2192'}</span>
                    <Select
                      value={columnMapping[csvCol] || ''}
                      onChange={(e) => handleMappingChange(csvCol, e.target.value)}
                      className="w-48"
                    >
                      {COLUMN_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </Select>
                    {preview.rows[0]?.[csvCol] && (
                      <span className="ml-auto truncate text-xs text-muted-foreground max-w-[200px]">
                        e.g. {preview.rows[0][csvCol]}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Preview Table */}
            <div className="space-y-3">
              <p className="text-sm font-medium">
                Preview (first {Math.min(preview.rows.length, 10)} rows)
              </p>
              <div className="overflow-x-auto rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      {Object.keys(preview.rows[0] || {}).map((col) => (
                        <TableHead key={col} className="whitespace-nowrap text-xs">
                          {col}
                          {columnMapping[col] && (
                            <Badge className="ml-1 text-[10px]" variant="secondary">
                              {columnMapping[col]}
                            </Badge>
                          )}
                        </TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {preview.rows.slice(0, 10).map((row, idx) => (
                      <TableRow key={idx}>
                        {Object.keys(row).map((col) => (
                          <TableCell key={col} className="text-xs whitespace-nowrap max-w-[200px] truncate">
                            {row[col]}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>

            {/* Errors/Warnings */}
            {preview.errors.length > 0 && (
              <div className="space-y-1 rounded-md border border-amber-500/30 bg-amber-500/10 p-3">
                <p className="text-sm font-medium text-amber-400">Warnings</p>
                {preview.errors.map((err, i) => (
                  <p key={i} className="text-xs text-amber-400/80">{err}</p>
                ))}
              </div>
            )}

            <div className="flex items-center justify-between">
              <Button variant="outline" onClick={handleReset}>
                Back
              </Button>
              <div className="flex items-center gap-3">
                <span className="text-sm text-muted-foreground">
                  {mappedFieldCount} field(s) mapped
                </span>
                <Button
                  onClick={() => setStep(3)}
                  disabled={!hasValueMapping}
                >
                  Continue
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 3: Confirm */}
      {step === 3 && file && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Confirm Import</CardTitle>
            <CardDescription>Review the import details before proceeding.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4 rounded-md border border-border p-4">
              <div>
                <p className="text-sm text-muted-foreground">File</p>
                <p className="font-medium text-sm">{file.name}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Format</p>
                <Badge variant="secondary">
                  {format === 'csv' ? 'CSV' : 'STIX 2.1 JSON'}
                </Badge>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Size</p>
                <p className="font-medium text-sm">
                  {(file.size / 1024).toFixed(1)} KB
                </p>
              </div>
              {preview && (
                <div>
                  <p className="text-sm text-muted-foreground">Rows</p>
                  <p className="font-medium text-sm">
                    {preview.total_rows.toLocaleString()}
                  </p>
                </div>
              )}
            </div>

            {format === 'csv' && (
              <div className="space-y-2">
                <p className="text-sm font-medium">Column Mapping</p>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(columnMapping)
                    .filter(([, v]) => v)
                    .map(([csvCol, field]) => (
                      <Badge key={csvCol} variant="outline" className="text-xs">
                        {csvCol} {'\u2192'} {field}
                      </Badge>
                    ))}
                </div>
              </div>
            )}

            <div className="flex items-center justify-between">
              <Button
                variant="outline"
                onClick={() => setStep(format === 'csv' ? 2 : 1)}
              >
                Back
              </Button>
              <Button onClick={handleConfirmImport} disabled={isImporting}>
                {isImporting ? 'Importing...' : 'Start Import'}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 4: Results */}
      {step === 4 && results && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Import Complete</CardTitle>
            <CardDescription>Here are the results of your import.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div className="rounded-md border border-green-500/30 bg-green-500/10 p-4 text-center">
                <p className="text-2xl font-bold text-green-400">{results.imported}</p>
                <p className="text-sm text-green-400/80">Imported</p>
              </div>
              <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-4 text-center">
                <p className="text-2xl font-bold text-amber-400">{results.skipped}</p>
                <p className="text-sm text-amber-400/80">Skipped</p>
              </div>
              <div className="rounded-md border border-red-500/30 bg-red-500/10 p-4 text-center">
                <p className="text-2xl font-bold text-red-400">{results.errors.length}</p>
                <p className="text-sm text-red-400/80">Errors</p>
              </div>
            </div>

            {results.errors.length > 0 && (
              <div className="space-y-1 rounded-md border border-red-500/30 bg-red-500/10 p-3 max-h-48 overflow-y-auto">
                <p className="text-sm font-medium text-red-400">Errors</p>
                {results.errors.map((err, i) => (
                  <p key={i} className="text-xs text-red-400/80 font-mono">{err}</p>
                ))}
              </div>
            )}

            <div className="flex justify-end">
              <Button onClick={handleReset}>Import Another File</Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
