"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api-client";

/* ── Types ─────────────────────────────────────────────── */

interface ICP {
  id: string;
  name: string;
  is_active: boolean;
}

interface TAMCell {
  dimension_x: string;
  dimension_y: string;
  total_estimated: number;
  captured: number;
  in_sequence: number;
  replied: number;
  coverage_pct: number;
}

interface TAMHeatmap {
  icp_id: string;
  x_dimension: string;
  y_dimension: string;
  cells: TAMCell[];
  total_tam_size: number;
  total_captured: number;
  overall_coverage_pct: number;
}

function cellColor(pct: number): string {
  if (pct === 0) return "bg-gray-100 text-gray-600";
  if (pct < 10) return "bg-blue-50 text-blue-700";
  if (pct < 25) return "bg-blue-100 text-blue-800";
  if (pct < 50) return "bg-blue-200 text-blue-900";
  return "bg-green-200 text-green-900";
}

/* ── TAM Explorer Page ─────────────────────────────────── */

export default function TAMPage() {
  const [icps, setICPs] = useState<ICP[]>([]);
  const [selectedICP, setSelectedICP] = useState<string>("");
  const [heatmap, setHeatmap] = useState<TAMHeatmap | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadICPs() {
    try {
      const data = await api.get<ICP[]>("/icps");
      setICPs(data);
      if (data.length > 0 && !selectedICP) {
        setSelectedICP(data[0].id);
      }
    } catch (err) {
      console.error("Failed to load ICPs:", err);
    }
  }

  async function loadHeatmap(icpId: string) {
    if (!icpId) return;
    setLoading(true);
    try {
      const data = await api.get<TAMHeatmap>("/tam/heatmap", {
        icp_id: icpId,
      });
      setHeatmap(data);
    } catch (err) {
      console.error("Failed to load heatmap:", err);
      setHeatmap(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadICPs();
  }, []);

  useEffect(() => {
    if (selectedICP) loadHeatmap(selectedICP);
  }, [selectedICP]);

  // Derive unique axes from cells
  const xValues = heatmap
    ? [...new Set(heatmap.cells.map((c) => c.dimension_x))]
    : [];
  const yValues = heatmap
    ? [...new Set(heatmap.cells.map((c) => c.dimension_y))]
    : [];

  function getCell(x: string, y: string): TAMCell | undefined {
    return heatmap?.cells.find(
      (c) => c.dimension_x === x && c.dimension_y === y,
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">TAM Explorer</h2>
          <p className="text-muted-foreground">
            Visualize market coverage and discover whitespace.
          </p>
        </div>
        <div className="w-64">
          <Select value={selectedICP} onValueChange={setSelectedICP}>
            <SelectTrigger>
              <SelectValue placeholder="Select ICP" />
            </SelectTrigger>
            <SelectContent>
              {icps.map((icp) => (
                <SelectItem key={icp.id} value={icp.id}>
                  {icp.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Summary bar */}
      {heatmap && (
        <div className="flex gap-4">
          <Card className="flex-1">
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold">
                {heatmap.total_tam_size.toLocaleString()}
              </p>
              <p className="text-xs text-muted-foreground">Total TAM</p>
            </CardContent>
          </Card>
          <Card className="flex-1">
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold">
                {heatmap.total_captured.toLocaleString()}
              </p>
              <p className="text-xs text-muted-foreground">
                Captured ({heatmap.overall_coverage_pct}%)
              </p>
            </CardContent>
          </Card>
          <Card className="flex-1">
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold">
                {heatmap.cells.filter((c) => c.in_sequence > 0).length}
              </p>
              <p className="text-xs text-muted-foreground">
                Cells with Active Sequences
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Heatmap grid */}
      {loading ? (
        <p className="text-muted-foreground">Loading heatmap...</p>
      ) : !heatmap ? (
        <p className="text-muted-foreground">
          {icps.length === 0
            ? "Create an ICP first to view TAM data."
            : "Select an ICP to view the heatmap."}
        </p>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Coverage Heatmap</CardTitle>
            <CardDescription>
              Industry (X) vs Company Size (Y). Click grey cells to discover
              whitespace.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr>
                    <th className="p-2 text-left font-medium text-muted-foreground">
                      Size \ Industry
                    </th>
                    {xValues.map((x) => (
                      <th key={x} className="p-2 text-center font-medium">
                        {x}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {yValues.map((y) => (
                    <tr key={y}>
                      <td className="p-2 font-medium text-muted-foreground">
                        {y}
                      </td>
                      {xValues.map((x) => {
                        const cell = getCell(x, y);
                        if (!cell) return <td key={x} className="p-2" />;
                        return (
                          <td key={x} className="p-1">
                            <div
                              className={`rounded-md p-3 text-center ${cellColor(
                                cell.coverage_pct,
                              )}`}
                            >
                              <p className="text-lg font-bold">
                                {cell.coverage_pct}%
                              </p>
                              <p className="text-xs">
                                {cell.captured} captured
                              </p>
                              {cell.in_sequence > 0 && (
                                <p className="text-xs">
                                  {cell.in_sequence} in sequence
                                </p>
                              )}
                            </div>
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
      )}
    </div>
  );
}
