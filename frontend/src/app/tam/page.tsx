"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api-client";

type ICP = {
  id: string;
  name: string;
  is_active: boolean;
};

type TAMCell = {
  dimension_x: string;
  dimension_y: string;
  total_estimated: number;
  captured: number;
  in_sequence: number;
  replied: number;
  coverage_pct: number;
};

type TAMHeatmap = {
  icp_id: string;
  x_dimension: string;
  y_dimension: string;
  cells: TAMCell[];
  total_tam_size: number;
  total_captured: number;
  overall_coverage_pct: number;
};

type YCImportResult = {
  imported: number;
};

function cellColor(pct: number): string {
  if (pct === 0) return "bg-gray-100 text-gray-700 hover:bg-gray-200";
  if (pct < 10) return "bg-blue-50 text-blue-700 hover:bg-blue-100";
  if (pct < 25) return "bg-blue-100 text-blue-800 hover:bg-blue-200";
  if (pct < 50) return "bg-blue-200 text-blue-900 hover:bg-blue-300";
  return "bg-green-200 text-green-900 hover:bg-green-300";
}

export default function TAMPage() {
  const queryClient = useQueryClient();
  const [isMounted, setIsMounted] = useState(false);

  const icpsQuery = useQuery({
    queryKey: ["icps"],
    queryFn: () => api.get<ICP[]>("/icps"),
  });

  const selectedICP = icpsQuery.data?.[0]?.id ?? "";
  const heatmapQuery = useQuery({
    queryKey: ["tam-heatmap", selectedICP],
    queryFn: () => api.get<TAMHeatmap>("/tam/heatmap", { icp_id: selectedICP }),
    enabled: Boolean(selectedICP),
  });

  const [activeICP, setActiveICP] = useState("");
  const [selectedCell, setSelectedCell] = useState<TAMCell | null>(null);
  const currentICP = activeICP || selectedICP;

  useEffect(() => {
    setIsMounted(true);
  }, []);

  const currentHeatmapQuery = useQuery({
    queryKey: ["tam-heatmap", currentICP],
    queryFn: () => api.get<TAMHeatmap>("/tam/heatmap", { icp_id: currentICP }),
    enabled: Boolean(currentICP),
    initialData: currentICP === selectedICP ? heatmapQuery.data : undefined,
  });

  const mockImportMutation = useMutation({
    mutationFn: () => api.post<YCImportResult>("/leads/import/yc", { batch: "W25", limit: 5 }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["tam-heatmap"] });
      setSelectedCell(null);
    },
  });

  const heatmap = currentHeatmapQuery.data;
  const xValues = heatmap ? [...new Set(heatmap.cells.map((cell) => cell.dimension_x))] : [];
  const yValues = heatmap ? [...new Set(heatmap.cells.map((cell) => cell.dimension_y))] : [];
  const chartData = heatmap
    ? xValues.map((industry) => ({
        industry,
        captured: heatmap.cells
          .filter((cell) => cell.dimension_x === industry)
          .reduce((sum, cell) => sum + cell.captured, 0),
      }))
    : [];

  function getCell(x: string, y: string) {
    return heatmap?.cells.find((cell) => cell.dimension_x === x && cell.dimension_y === y);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">TAM Explorer</h2>
          <p className="text-muted-foreground">Visualize market coverage and turn whitespace into lead discovery actions.</p>
        </div>
        <div className="w-64">
          <Select value={currentICP} onValueChange={setActiveICP}>
            <SelectTrigger><SelectValue placeholder="Select ICP" /></SelectTrigger>
            <SelectContent>
              {icpsQuery.data?.map((icp) => (
                <SelectItem key={icp.id} value={icp.id}>{icp.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {heatmap && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <Card><CardContent className="p-4 text-center"><p className="text-2xl font-bold">{heatmap.total_tam_size.toLocaleString()}</p><p className="text-xs text-muted-foreground">Total TAM</p></CardContent></Card>
          <Card><CardContent className="p-4 text-center"><p className="text-2xl font-bold">{heatmap.total_captured.toLocaleString()}</p><p className="text-xs text-muted-foreground">Captured</p></CardContent></Card>
          <Card><CardContent className="p-4 text-center"><p className="text-2xl font-bold">{heatmap.overall_coverage_pct}%</p><p className="text-xs text-muted-foreground">Coverage</p></CardContent></Card>
          <Card><CardContent className="p-4 text-center"><p className="text-2xl font-bold">{heatmap.cells.filter((cell) => cell.coverage_pct === 0).length}</p><p className="text-xs text-muted-foreground">Grey Cells</p></CardContent></Card>
        </div>
      )}

      {heatmap && (
        <Card>
          <CardHeader>
            <CardTitle>Captured Leads by Industry</CardTitle>
            <CardDescription>Recharts view for quick coverage comparison.</CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            {isMounted && (
              <ResponsiveContainer width="100%" height="100%" minHeight={220}>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="industry" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar
                    dataKey="captured"
                    fill="var(--primary)"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      )}

      {currentHeatmapQuery.isLoading ? (
        <p className="text-muted-foreground">Loading heatmap...</p>
      ) : !heatmap ? (
        <p className="text-muted-foreground">Create an ICP first to view TAM data.</p>
      ) : (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_360px]">
          <Card>
            <CardHeader>
              <CardTitle>Coverage Heatmap</CardTitle>
              <CardDescription>Click a grey or low-coverage cell to open Discover Leads.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr>
                      <th className="p-2 text-left font-medium text-muted-foreground">Size \ Industry</th>
                      {xValues.map((x) => <th key={x} className="p-2 text-center font-medium">{x}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {yValues.map((y) => (
                      <tr key={y}>
                        <td className="p-2 font-medium text-muted-foreground">{y}</td>
                        {xValues.map((x) => {
                          const cell = getCell(x, y);
                          if (!cell) return <td key={x} className="p-2" />;
                          return (
                            <td key={x} className="p-1">
                              <button
                                type="button"
                                onClick={() => setSelectedCell(cell)}
                                className={`w-full rounded-md p-3 text-center transition-colors ${cellColor(cell.coverage_pct)}`}
                              >
                                <p className="text-lg font-bold">{cell.coverage_pct}%</p>
                                <p className="text-xs">{cell.captured} captured</p>
                                {cell.in_sequence > 0 && <p className="text-xs">{cell.in_sequence} in sequence</p>}
                              </button>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Discover Leads</CardTitle>
              <CardDescription>Whitespace action panel for the selected TAM cell.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {selectedCell ? (
                <>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between"><span className="text-muted-foreground">Industry</span><Badge variant="secondary">{selectedCell.dimension_x}</Badge></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">Company size</span><Badge variant="secondary">{selectedCell.dimension_y}</Badge></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">Coverage</span><span>{selectedCell.coverage_pct}%</span></div>
                  </div>
                  <Button type="button" variant="outline" className="w-full" disabled>
                    Real-source discovery not wired yet
                  </Button>
                  <Button type="button" className="w-full" onClick={() => mockImportMutation.mutate()} disabled={mockImportMutation.isPending}>
                    {mockImportMutation.isPending ? "Importing..." : "Run Mock YC Import"}
                  </Button>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">Select a grey or low-coverage heatmap cell to prepare a discovery action.</p>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
