import { useCallback } from 'react';
import { useReactFlow, Node, Edge } from 'reactflow';
import { toPng } from 'html-to-image';
import { ExportOptions } from '../types';
import { AttackFlowNode, FlowEdge } from '../../types/attack-flow';
import { STIXBundleExporter } from '../../../flow-export/services/stixBundleExporter';
import { SavedFlow } from '../../../flow-storage/types/SavedFlow';

interface ExportData {
  nodes: AttackFlowNode[];
  edges: FlowEdge[];
  sourceUrl?: string;
  sourceText?: string;
  inputMode?: 'url' | 'text';
}

export const useExportFlow = (data: ExportData) => {
  const { getViewport } = useReactFlow();

  const exportToPng = useCallback(async (filename: string = 'attack-flow') => {
    const element = document.querySelector('.react-flow') as HTMLElement;
    if (!element) return;

    try {
      const dataUrl = await toPng(element, {
        backgroundColor: '#0d1117',
        width: element.offsetWidth,
        height: element.offsetHeight,
        style: {
          transform: 'none',
        },
      });

      const link = document.createElement('a');
      link.download = `${filename}.png`;
      link.href = dataUrl;
      link.click();
    } catch (error) {
      console.error('Error exporting to PNG:', error);
    }
  }, []);

  const exportToJson = useCallback((filename: string = 'attack-flow') => {
    const nodes: Node[] = data.nodes.map((node, index) => ({
      id: node.id || `node-${index}`,
      type: node.type,
      data: node,
      position: { x: 0, y: 0 }
    }));

    const edges: Edge[] = data.edges.map((edge, index) => ({
      id: edge.id || `edge-${index}`,
      source: edge.source,
      target: edge.target,
      label: edge.label,
      type: 'default'
    }));

    const exporter = new STIXBundleExporter();
    const stixBundle = exporter.exportToSTIXBundle(nodes, edges);

    const exportData = {
      ...stixBundle,
      x_flowviz_metadata: {
        viewport: getViewport(),
        exportedAt: new Date().toISOString(),
        tool: 'FlowViz',
        version: '1.0.0'
      }
    };

    const dataStr = JSON.stringify(exportData, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);

    const link = document.createElement('a');
    link.download = `${filename}-stix.json`;
    link.href = url;
    link.click();

    URL.revokeObjectURL(url);
  }, [data, getViewport]);

  const exportToFlowViz = useCallback((filename: string = 'attack-flow') => {
    const nodes: Node[] = data.nodes.map((node, index) => ({
      id: node.id || `node-${index}`,
      type: node.type,
      data: node,
      position: { x: 0, y: 0 }
    }));

    const edges: Edge[] = data.edges.map((edge, index) => ({
      id: edge.id || `edge-${index}`,
      source: edge.source,
      target: edge.target,
      label: edge.label,
      type: 'default'
    }));

    const techniques: string[] = [];
    const tactics: string[] = [];

    data.nodes.forEach(node => {
      if (node.techniques) {
        techniques.push(...node.techniques);
      }
      if (node.tactics) {
        tactics.push(...node.tactics);
      }
    });

    const flowVizData: SavedFlow = {
      id: crypto.randomUUID(),
      title: filename,
      sourceUrl: data.sourceUrl,
      sourceText: data.sourceText,
      inputMode: data.inputMode || 'url',
      nodes,
      edges,
      metadata: {
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        version: '1.0.0',
        description: 'Exported from FlowViz',
        tags: [],
        nodeCount: nodes.length,
        edgeCount: edges.length,
      },
      visualization: {
        viewport: getViewport(),
        storyMode: { enabled: false }
      },
      analysis: {
        extractedTechniques: [...new Set(techniques)],
        extractedTactics: [...new Set(tactics)]
      }
    };

    const dataStr = JSON.stringify(flowVizData, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);

    const link = document.createElement('a');
    link.download = `${filename}-flowviz.json`;
    link.href = url;
    link.click();

    URL.revokeObjectURL(url);
  }, [data, getViewport]);

  const handleExport = useCallback((format: ExportOptions['format'], filename?: string) => {
    const exportFilename = filename || `attack-flow-${Date.now()}`;

    if (format === 'png') {
      exportToPng(exportFilename);
    } else if (format === 'json') {
      exportToJson(exportFilename);
    } else if (format === 'flowviz') {
      exportToFlowViz(exportFilename);
    }
  }, [exportToPng, exportToJson, exportToFlowViz]);

  return { handleExport };
};