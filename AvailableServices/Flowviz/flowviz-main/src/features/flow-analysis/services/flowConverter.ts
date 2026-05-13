import { v4 as uuidv4 } from 'uuid';
import { AttackFlowNode, FlowEdge } from '../types/attack-flow';
import { ExtractedAttackInfo } from './types';
import { TACTIC_DEFINITIONS } from './config';
// import { RelationshipAnalyzer } from './relationshipAnalyzer'; // REMOVED: Client-side API usage

export class FlowConverter {
  private nodes: AttackFlowNode[] = [];
  private edges: FlowEdge[] = [];
  private infrastructure: Map<string, string> = new Map();
  private processedActions: Map<string, string> = new Map();
  // private relationshipAnalyzer: RelationshipAnalyzer; // REMOVED: Client-side API usage
  
  constructor(apiKey?: string) {
    // this.relationshipAnalyzer = new RelationshipAnalyzer(apiKey); // REMOVED: Client-side API usage
    // Note: apiKey parameter kept for backward compatibility but no longer used
  }

  async convertToAttackFlow(extractedInfo: ExtractedAttackInfo): Promise<{ nodes: AttackFlowNode[], edges: FlowEdge[] }> {
    console.log('=== CONVERT TO ATTACK FLOW: Starting Conversion ===');
    
    this.resetState();
    
    // Create assets first so they exist when actions reference them
    this.createAssetNodes(extractedInfo);
    
    // Create action nodes in tactical order
    const createdTactics = await this.createActionNodes(extractedInfo);
    
    // Create additional nodes using official AFB types
    this.createOperatorNodes(extractedInfo);
    this.createVulnerabilityNodes(extractedInfo);
    this.createToolNodes(extractedInfo);
    this.createMalwareNodes(extractedInfo);
    this.createInfrastructureNodes(extractedInfo);
    this.createUrlNodes(extractedInfo);
    
    // Connect tactics
    this.connectTactics(createdTactics, extractedInfo);
    
    this.logFinalStatistics(createdTactics);
    
    return { nodes: this.nodes, edges: this.edges };
  }

  private resetState(): void {
    this.nodes = [];
    this.edges = [];
    this.infrastructure.clear();
    this.processedActions.clear();
  }

  private createAssetNodes(extractedInfo: ExtractedAttackInfo): void {
    console.log('=== Creating Asset Nodes ===');
    extractedInfo.assets?.forEach((asset, index) => {
      const id = `asset-${index}`;
      
      const assetNode: AttackFlowNode = {
        id,
        type: 'asset',
        spec_version: '2.1',
        name: asset.name,
        description: asset.description,
        role: asset.role,
        impact: asset.impact,
        details: asset.details,
        asset_type: asset.asset_type || 'system',
        source_snippet: asset.source_snippet || '',
        confidence: asset.confidence || 'medium',
        affected_by: [],
      };
      
      this.nodes.push(assetNode);
      console.log(`Created asset node: ${asset.name} (${id})`);
    });
    
    // Create asset-to-asset connections
    this.createAssetConnections(extractedInfo);
  }
  
  private createAssetConnections(extractedInfo: ExtractedAttackInfo): void {
    extractedInfo.assets?.forEach((asset, index) => {
      const sourceId = `asset-${index}`;
      
      asset.connects_to?.forEach((targetAssetName: string) => {
        // Find the target asset by name
        const targetAssetIndex = extractedInfo.assets?.findIndex(a => a.name === targetAssetName);
        if (targetAssetIndex !== undefined && targetAssetIndex !== -1) {
          const targetId = `asset-${targetAssetIndex}`;
          
          this.edges.push({
            id: uuidv4(),
            source: sourceId,
            target: targetId,
            label: 'Connects to'
          });
          
          console.log(`Connected assets: ${asset.name} → ${targetAssetName}`);
        }
      });
    });
  }

  private async createActionNodes(extractedInfo: ExtractedAttackInfo): Promise<Array<{
    key: string;
    prefix: string;
    count: number;
    firstActionId: string;
    lastActionId: string;
  }>> {
    const presentTactics = this.determinePresentTactics(extractedInfo);
    const tacticalOrder = this.sortTacticsLogically(presentTactics, extractedInfo);
    
    console.log('=== Dynamic Tactical Ordering ===');
    console.log('Tactics present in this attack:');
    tacticalOrder.forEach((tactic, index) => {
      const actions = extractedInfo[tactic.key as keyof ExtractedAttackInfo] as any[];
      console.log(`${index + 1}. ${tactic.key} (${tactic.tacticId}): ${actions?.length || 0} actions`);
    });

    const createdTactics: Array<{
      key: string;
      prefix: string;
      count: number;
      firstActionId: string;
      lastActionId: string;
    }> = [];

    let globalActionIndex = 0;

    for (const { key, prefix, tacticId } of tacticalOrder) {
      const actions = extractedInfo[key as keyof ExtractedAttackInfo] as any[];
      if (!actions?.length) continue;

      console.log(`=== Creating ${key} nodes ===`);
      console.log(`Processing ${actions.length} ${key} actions`);

      let firstActionId = '';
      let currentLastActionId = '';
      let deduplicatedCount = 0;

      for (let index = 0; index < actions.length; index++) {
        const action = actions[index];
        const actionHash = `${action.technique || ''}_${(action.description || '').toLowerCase().trim()}`;
        const existingNodeId = this.processedActions.get(actionHash);
        
        let id: string;
        if (existingNodeId && action.technique) {
          id = existingNodeId;
          deduplicatedCount++;
          console.log(`Deduplicating action: ${action.name} (reusing ${id})`);
        } else {
          id = await this.createActionNode(action, globalActionIndex, tacticId, extractedInfo);
          if (action.technique) {
            this.processedActions.set(actionHash, id);
          }
          globalActionIndex++;
        }
        
        if (index === 0) {
          firstActionId = id;
        }
        
        // Connect sequential actions within the same tactic with LLM-enhanced logic
        if (index > 0 && currentLastActionId !== id) {
          const shouldConnect = await this.shouldConnectSequentialActionsWithLLM(actions[index - 1], action, index === 1);
          const edgeExists = this.edges.some(e => e.source === currentLastActionId && e.target === id);
          
          if (shouldConnect.connect && !edgeExists) {
            this.edges.push({
              id: uuidv4(),
              source: currentLastActionId,
              target: id,
              label: shouldConnect.relationshipType
            });
            console.log(`Connected sequential actions: ${currentLastActionId} -> ${id} (${shouldConnect.relationshipType}, confidence: ${shouldConnect.confidence})`);
          }
        }
        
        currentLastActionId = id;
      }
      
      createdTactics.push({ 
        key, 
        prefix, 
        count: actions.length - deduplicatedCount, 
        firstActionId, 
        lastActionId: currentLastActionId 
      });
      console.log(`Completed ${key} nodes: ${actions.length - deduplicatedCount} unique nodes created (${deduplicatedCount} duplicates removed)`);
    }

    return createdTactics;
  }

  private determinePresentTactics(extractedInfo: ExtractedAttackInfo) {
    return TACTIC_DEFINITIONS.filter(tactic => {
      const actions = extractedInfo[tactic.key as keyof ExtractedAttackInfo] as any[];
      return actions && actions.length > 0;
    });
  }

  private sortTacticsLogically(presentTactics: typeof TACTIC_DEFINITIONS[number][], extractedInfo: ExtractedAttackInfo) {
    return presentTactics.sort((a, b) => {
      const aActions = extractedInfo[a.key as keyof ExtractedAttackInfo] as any[];
      const bActions = extractedInfo[b.key as keyof ExtractedAttackInfo] as any[];
      
      if (!aActions?.length || !bActions?.length) return 0;
      
      // Check for temporal indicators
      const aHasEarly = aActions.some(action => 
        action.description?.toLowerCase().includes('first') || 
        action.description?.toLowerCase().includes('initial') ||
        action.description?.toLowerCase().includes('began') ||
        action.description?.toLowerCase().includes('started')
      );
      
      const bHasEarly = bActions.some(action => 
        action.description?.toLowerCase().includes('first') || 
        action.description?.toLowerCase().includes('initial') ||
        action.description?.toLowerCase().includes('began') ||
        action.description?.toLowerCase().includes('started')
      );
      
      if (aHasEarly && !bHasEarly) return -1;
      if (!aHasEarly && bHasEarly) return 1;
      
      // Fall back to standard MITRE ordering
      const aIndex = TACTIC_DEFINITIONS.findIndex(t => t.key === a.key);
      const bIndex = TACTIC_DEFINITIONS.findIndex(t => t.key === b.key);
      return aIndex - bIndex;
    });
  }

  private async createActionNode(action: any, index: number, tacticId?: string, extractedInfo?: ExtractedAttackInfo): Promise<string> {
    const id = `action-${index}`;
    
    const targetedAssets = this.getTargetedAssets(action, extractedInfo);
    
    const actionNode: AttackFlowNode = {
      id,
      type: 'attack-action',
      spec_version: '2.1',
      name: action.name || `Action ${index + 1}`,
      description: action.description || 'No description available',
      technique_id: action.technique || action.technique_id,
      tactic_id: tacticId,
      tactic_name: action.tacticName || action.tactic,
      source_excerpt: action.source_snippet || '',
      confidence: action.confidence || 'medium',
      targeted_assets: targetedAssets,
      asset_impact_level: (targetedAssets.length > 0 ? 
        (targetedAssets.length > 2 ? 'high' : 'medium') : 'low') as 'low' | 'medium' | 'high'
    };
    
    this.nodes.push(actionNode);
    console.log(`Created action node: ${actionNode.name}`, {
      technique_id: actionNode.technique_id,
      tactic: actionNode.tactic_name,
      targets_assets: targetedAssets.length,
      targeted_asset_ids: targetedAssets
    });
    
    // Create edges to targeted assets
    await this.connectToTargetedAssets(id, targetedAssets, actionNode);
    
    return id;
  }

  private getTargetedAssets(action: any, extractedInfo?: ExtractedAttackInfo): string[] {
    const targetedAssets: string[] = [];
    
    // First priority: Use explicit targets_assets from Claude
    if (action.targets_assets && Array.isArray(action.targets_assets)) {
      action.targets_assets.forEach((targetAssetName: string) => {
        // Find matching asset by name
        extractedInfo?.assets?.forEach((asset, assetIndex) => {
          if (asset.name && asset.name.toLowerCase() === targetAssetName.toLowerCase()) {
            targetedAssets.push(`asset-${assetIndex}`);
            console.log(`✅ Action "${action.name}" explicitly targets asset: ${asset.name} (asset-${assetIndex})`);
          }
        });
      });
    }
    
    // Fallback: Try to infer from action description if no explicit targets
    if (targetedAssets.length === 0) {
      const description = (action.description || '').toLowerCase();
      
      extractedInfo?.assets?.forEach((asset, assetIndex) => {
        const assetName = (asset.name || '').toLowerCase();
        
        // Check if action mentions this asset directly
        if (description.includes(assetName)) {
          targetedAssets.push(`asset-${assetIndex}`);
          console.log(`🔍 Action "${action.name}" inferred to target asset: ${asset.name} (asset-${assetIndex})`);
        }
      });
    }
    
    return targetedAssets;
  }

  private async connectToTargetedAssets(actionId: string, targetedAssets: string[], actionNode: AttackFlowNode): Promise<void> {
    if (targetedAssets.length === 0) return;
    
    // Prepare batch analysis requests
    const analysisRequests = targetedAssets.map(assetId => {
      const assetNode = this.nodes.find(node => node.id === assetId);
      if (!assetNode) return null;
      
      return {
        assetId,
        request: {
          actionName: actionNode.name,
          actionDescription: (actionNode as any).description || '',
          actionTechnique: (actionNode as any).technique_id,
          assetName: assetNode.name,
          assetType: (assetNode as any).asset_type,
          assetRole: (assetNode as any).role
        }
      };
    }).filter(req => req !== null);
    
    // Batch analyze relationships - REMOVED: Now handled server-side
    // const relationships = await this.relationshipAnalyzer.analyzeBatchRelationships(
    //   analysisRequests.map(req => req!.request)
    // );
    const relationships: any[] = []; // Fallback to simple sequential connections
    
    // Create edges and update assets
    analysisRequests.forEach((req, index) => {
      if (!req) return;
      
      const relationship = relationships[index];
      const assetNode = this.nodes.find(node => node.id === req.assetId);
      
      this.edges.push({
        id: uuidv4(),
        source: actionId,
        target: req.assetId,
        label: relationship.label,
      });
      
      if (assetNode && assetNode.type === 'asset') {
        if (!assetNode.affected_by) {
          assetNode.affected_by = [];
        }
        assetNode.affected_by.push(actionId);
        console.log(`Action ${actionNode.name} ${relationship.label.toLowerCase()} asset ${assetNode.name} (confidence: ${relationship.confidence})`);
      }
    });
  }

  private createOperatorNodes(extractedInfo: ExtractedAttackInfo): void {
    console.log('=== Creating Operator Nodes ===');
    extractedInfo.operators?.forEach((operator, index) => {
      const id = `operator-${index}`;
      
      this.nodes.push({
        id,
        type: operator.operator === 'AND' ? 'AND_operator' : 'OR_operator',
        spec_version: '2.1',
        name: operator.name || `Operator ${index + 1}`,
        operator: operator.operator,
      });
      
      console.log(`Created operator node: ${operator.name} (${operator.operator})`);
      
      // Connect input conditions to operator
      this.connectOperatorInputs(operator, id);
      
      // Connect operator to output actions
      this.connectOperatorOutputs(operator, id);
    });
  }

  private connectOperatorInputs(operator: any, operatorId: string): void {
    operator.input_conditions?.forEach((conditionName: string) => {
      const conditionNode = this.nodes.find(n => 
        (n.type === 'AND_operator' || n.type === 'OR_operator') && n.name === conditionName
      );
      if (conditionNode) {
        this.edges.push({
          id: uuidv4(),
          source: conditionNode.id,
          target: operatorId,
          label: 'Feeds into'
        });
        console.log(`Connected condition "${conditionName}" to operator "${operator.name}"`);
      }
    });
  }

  private connectOperatorOutputs(operator: any, operatorId: string): void {
    operator.output_actions?.forEach((actionTechniqueId: string) => {
      const actionNode = this.nodes.find(n => 
        n.type === 'attack-action' && n.technique_id === actionTechniqueId
      );
      if (actionNode) {
        this.edges.push({
          id: uuidv4(),
          source: operatorId,
          target: actionNode.id,
          label: operator.operator === 'AND' ? 'All required for' : 'Enables'
        });
        console.log(`Connected operator "${operator.name}" to action "${actionNode.name}"`);
      }
    });
  }

  private createVulnerabilityNodes(extractedInfo: ExtractedAttackInfo): void {
    console.log('=== Creating Vulnerability Nodes ===');
    extractedInfo.vulnerabilities?.forEach((vuln, index) => {
      // Only create nodes for vulnerabilities with CVE identifiers
      const cvePattern = /CVE-\d{4}-\d+/i;
      const hasCVE = vuln.name.match(cvePattern) || vuln.cve_id?.match(cvePattern);
      
      if (!hasCVE) {
        console.log(`Skipping non-CVE vulnerability: ${vuln.name} (no CVE identifier)`);
        return;
      }
      
      const id = `vulnerability-${index}`;
      
      this.nodes.push({
        id,
        type: 'vulnerability',
        spec_version: '2.1',
        name: vuln.name,
        description: vuln.description,
        cve_id: vuln.cve_id,
        cvss_score: vuln.cvss_score,
        source_snippet: vuln.source_snippet || '',
        confidence: vuln.confidence || 'medium',
      });
      
      console.log(`Created vulnerability node: ${vuln.name} (${vuln.cve_id || 'CVE from name'})`);
      
      this.connectVulnerabilityToAssets(vuln, id);
      this.connectVulnerabilityToActions(vuln, id);
    });
  }

  private connectVulnerabilityToAssets(vuln: any, vulnId: string): void {
    vuln.affects_assets?.forEach((assetName: string) => {
      const assetNode = this.nodes.find(n => n.type === 'asset' && n.name === assetName);
      if (assetNode) {
        this.edges.push({
          id: uuidv4(),
          source: vulnId,
          target: assetNode.id,
          label: 'Affects'
        });
        console.log(`Vulnerability "${vuln.name}" affects asset "${assetName}"`);
      }
    });
  }

  private connectVulnerabilityToActions(vuln: any, vulnId: string): void {
    vuln.exploited_by?.forEach((techniqueId: string) => {
      const actionNode = this.nodes.find(n => n.type === 'attack-action' && n.technique_id === techniqueId);
      if (actionNode) {
        this.edges.push({
          id: uuidv4(),
          source: vulnId,
          target: actionNode.id,
          label: 'Exploited by'
        });
        console.log(`Vulnerability "${vuln.name}" exploited by action "${actionNode.name}"`);
      }
    });
  }

  private createToolNodes(extractedInfo: ExtractedAttackInfo): void {
    console.log('=== Creating Tool Nodes ===');
    extractedInfo.tools?.forEach((tool, index) => {
      const id = `tool-${index}`;
      
      this.nodes.push({
        id,
        type: 'tool',
        spec_version: '2.1',
        name: tool.name,
        description: tool.description,
        command_line: tool.command_line && tool.command_line.trim() ? tool.command_line : undefined,
        tool_types: [tool.tool_type || 'software'],
        source_snippet: tool.source_snippet || '',
        confidence: tool.confidence || 'medium',
      });
      
      console.log(`Created tool node: ${tool.name} (command: ${tool.command_line || 'none'})`);
      
      this.connectToolToActions(tool, id);
      this.connectToolToAssets(tool, id);
    });
  }

  private connectToolToActions(tool: any, toolId: string): void {
    tool.used_by?.forEach((techniqueId: string) => {
      const actionNode = this.nodes.find(n => n.type === 'attack-action' && n.technique_id === techniqueId);
      if (actionNode) {
        this.edges.push({
          id: uuidv4(),
          source: actionNode.id,
          target: toolId,
          label: 'Uses'
        });
        console.log(`✅ Connected: Action "${actionNode.name}" uses tool "${tool.name}"`);
      } else {
        console.log(`❌ No action found with technique ID: ${techniqueId} for tool "${tool.name}"`);
      }
    });
  }

  private connectToolToAssets(tool: any, toolId: string): void {
    tool.targets_assets?.forEach((assetName: string) => {
      const assetNode = this.nodes.find(n => n.type === 'asset' && n.name === assetName);
      if (assetNode) {
        this.edges.push({
          id: uuidv4(),
          source: toolId,
          target: assetNode.id,
          label: 'Targets'
        });
        console.log(`Tool "${tool.name}" targets asset "${assetName}"`);
      }
    });
  }

  private createMalwareNodes(extractedInfo: ExtractedAttackInfo): void {
    console.log('=== Creating Malware Nodes ===');
    extractedInfo.malware?.forEach((malware, index) => {
      const id = `malware-${index}`;
      
      this.nodes.push({
        id,
        type: 'malware',
        spec_version: '2.1',
        name: malware.name,
        description: malware.description,
        command_line: malware.command_line && malware.command_line.trim() ? malware.command_line : undefined,
        malware_types: [malware.malware_type || 'unknown'],
        source_snippet: malware.source_snippet || '',
        confidence: malware.confidence || 'medium',
      });
      
      console.log(`Created malware node: ${malware.name} (command: ${malware.command_line || 'none'})`);
      
      this.connectMalwareToActions(malware, id);
      this.connectMalwareToAssets(malware, id);
    });
  }

  private connectMalwareToActions(malware: any, malwareId: string): void {
    malware.used_by?.forEach((techniqueId: string) => {
      const actionNode = this.nodes.find(n => n.type === 'attack-action' && n.technique_id === techniqueId);
      if (actionNode) {
        this.edges.push({
          id: uuidv4(),
          source: actionNode.id,
          target: malwareId,
          label: 'Uses'
        });
        console.log(`✅ Connected: Action "${actionNode.name}" uses malware "${malware.name}"`);
      } else {
        console.log(`❌ No action found with technique ID: ${techniqueId} for malware "${malware.name}"`);
      }
    });
  }

  private connectMalwareToAssets(malware: any, malwareId: string): void {
    malware.targets_assets?.forEach((assetName: string) => {
      const assetNode = this.nodes.find(n => n.type === 'asset' && n.name === assetName);
      if (assetNode) {
        this.edges.push({
          id: uuidv4(),
          source: malwareId,
          target: assetNode.id,
          label: 'Targets'
        });
        console.log(`Malware "${malware.name}" targets asset "${assetName}"`);
      }
    });
  }

  private createUrlNodes(extractedInfo: ExtractedAttackInfo): void {
    console.log('=== Creating URL Nodes ===');
    extractedInfo.urls?.forEach((url, index) => {
      const id = `url-${index}`;
      
      this.nodes.push({
        id,
        type: 'url',
        spec_version: '2.1',
        name: url.name.length > 50 ? url.name.substring(0, 47) + '...' : url.name,
        description: url.description,
        value: url.value || url.name,
        source_snippet: url.source_snippet || '',
        confidence: url.confidence || 'medium',
      });
      
      console.log(`Created URL node: ${url.name}`);
      
      this.connectUrlToActions(url, id);
    });
  }

  private connectUrlToActions(url: any, urlId: string): void {
    url.used_by?.forEach((techniqueId: string) => {
      const actionNode = this.nodes.find(n => n.type === 'attack-action' && n.technique_id === techniqueId);
      if (actionNode) {
        this.edges.push({
          id: uuidv4(),
          source: actionNode.id,
          target: urlId,
          label: 'Uses'
        });
        console.log(`✅ Connected: Action "${actionNode.name}" uses URL "${url.name}"`);
      } else {
        console.log(`❌ No action found with technique ID: ${techniqueId} for URL "${url.name}"`);
      }
    });
  }

  private createProcessNodes(extractedInfo: ExtractedAttackInfo): void {
    console.log('=== Creating Process Nodes (as Tools) ===');
    extractedInfo.processes?.forEach((process, index) => {
      const id = `process-${index}`;
      
      this.nodes.push({
        id,
        type: 'tool',
        spec_version: '2.1',
        name: process.name,
        description: process.description,
        command_line: process.command_line,
        tool_types: [process.process_type || 'process'],
        source_snippet: process.source_snippet || '',
        confidence: process.confidence || 'medium',
      });
      
      console.log(`Created tool node from process: ${process.name} (${process.process_type})`);
      
      this.connectProcessToAssets(process, id);
    });
  }

  private connectProcessToAssets(process: any, processId: string): void {
    process.affected_assets?.forEach((assetName: string) => {
      const assetNode = this.nodes.find(n => n.type === 'attack-asset' && n.name === assetName);
      if (assetNode) {
        this.edges.push({
          id: uuidv4(),
          source: processId,
          target: assetNode.id,
          label: 'Runs on'
        });
        console.log(`Process "${process.name}" runs on asset "${assetName}"`);
      }
    });
  }

  private createFileNodes(extractedInfo: ExtractedAttackInfo): void {
    console.log('=== Creating File Nodes ===');
    extractedInfo.files?.forEach((file, index) => {
      const id = `file-${index}`;
      
      this.nodes.push({
        id,
        type: 'file',
        spec_version: '2.1',
        name: file.name,
        description: file.description,
        file_type: file.file_type,
        path: file.path,
        hash: file.hash,
        size: file.size ? parseInt(file.size) : undefined,
        source_snippet: file.source_snippet || '',
        confidence: file.confidence || 'medium',
      });
      
      console.log(`Created file node: ${file.name} (${file.file_type})`);
      
      this.connectFileToAssets(file, id);
    });
  }

  private connectFileToAssets(file: any, fileId: string): void {
    file.deployed_to?.forEach((assetName: string) => {
      const assetNode = this.nodes.find(n => n.type === 'attack-asset' && n.name === assetName);
      if (assetNode) {
        this.edges.push({
          id: uuidv4(),
          source: fileId,
          target: assetNode.id,
          label: 'Deployed to'
        });
        console.log(`File "${file.name}" deployed to asset "${assetName}"`);
      }
    });
  }

  private createIndicatorAssets(extractedInfo: ExtractedAttackInfo): void {
    console.log('=== Creating Indicator Assets ===');
    
    this.createIPAddressAssets(extractedInfo);
    this.createDomainAssets(extractedInfo);
    this.createFileHashAssets(extractedInfo);
    this.createURLAssets(extractedInfo);
    this.createUserAccountAssets(extractedInfo);
    this.createRegistryKeyAssets(extractedInfo);
    this.createNetworkPortAssets(extractedInfo);
  }

  private createIPAddressAssets(extractedInfo: ExtractedAttackInfo): void {
    extractedInfo.indicators?.ip_addresses?.forEach((ip, index) => {
      const id = `indicator-ip-${index}`;
      
      this.nodes.push({
        id,
        type: 'attack-asset',
        spec_version: '2.1',
        name: ip.value,
        description: ip.description,
        role: 'Network Indicator',
        asset_type: 'network-infrastructure',
        indicator_type: 'ip-address',
        indicator_value: ip.value,
        indicator_reputation: ip.reputation,
        ip_type: ip.ip_type,
        source_snippet: ip.source_snippet || '',
        confidence: ip.confidence || 'medium',
      });
      
      console.log(`Created IP address asset: ${ip.value} (${ip.reputation || 'unknown'})`);
      
      this.connectIndicatorToTechniques(ip.used_by || [], id, 'Uses');
    });
  }

  private createDomainAssets(extractedInfo: ExtractedAttackInfo): void {
    extractedInfo.indicators?.domains?.forEach((domain, index) => {
      const id = `indicator-domain-${index}`;
      
      this.nodes.push({
        id,
        type: 'attack-asset',
        spec_version: '2.1',
        name: domain.value,
        description: domain.description,
        role: 'Network Indicator',
        asset_type: 'network-infrastructure',
        indicator_type: 'domain',
        indicator_value: domain.value,
        indicator_reputation: domain.reputation,
        domain_type: domain.domain_type,
        source_snippet: domain.source_snippet || '',
        confidence: domain.confidence || 'medium',
      });
      
      console.log(`Created domain asset: ${domain.value} (${domain.reputation || 'unknown'})`);
      
      this.connectIndicatorToTechniques(domain.used_by || [], id, 'Uses');
    });
  }

  private createFileHashAssets(extractedInfo: ExtractedAttackInfo): void {
    extractedInfo.indicators?.file_hashes?.forEach((hash, index) => {
      const id = `indicator-hash-${index}`;
      const hashType = hash.hash_type || 'HASH';
      const fileName = hash.file_name || '';
      const hashValue = hash.value || '';
      
      this.nodes.push({
        id,
        type: 'attack-asset',
        spec_version: '2.1',
        name: `${hashType.toUpperCase()}: ${hashValue.substring(0, 16)}...`,
        description: fileName ? `${hashType.toUpperCase()} hash of ${fileName}` : hash.description || `${hashType.toUpperCase()} hash`,
        role: 'File Indicator',
        asset_type: 'data',
        indicator_type: 'file-hash',
        indicator_value: hashValue,
        indicator_reputation: hash.reputation,
        hash_type: hash.hash_type,
        source_snippet: hash.source_snippet || '',
        confidence: hash.confidence || 'medium',
      });
      
      console.log(`Created file hash asset: ${hashType.toUpperCase()}:${hashValue.substring(0, 8)}... (${hash.reputation || 'unknown'})`);
      
      // Connect to associated files
      this.connectHashToFiles(hash, id);
    });
  }

  private createURLAssets(extractedInfo: ExtractedAttackInfo): void {
    extractedInfo.indicators?.urls?.forEach((url, index) => {
      const id = `indicator-url-${index}`;
      
      this.nodes.push({
        id,
        type: 'attack-asset',
        spec_version: '2.1',
        name: url.value.length > 50 ? url.value.substring(0, 47) + '...' : url.value,
        description: url.description,
        role: 'Network Indicator',
        asset_type: 'web-infrastructure',
        indicator_type: 'url',
        indicator_value: url.value,
        indicator_reputation: url.reputation,
        source_snippet: url.source_snippet || '',
        confidence: url.confidence || 'medium',
      });
      
      console.log(`Created URL asset: ${url.value} (${url.reputation || 'unknown'})`);
      
      this.connectIndicatorToTechniques(url.used_by || [], id, 'Uses');
    });
  }

  private createUserAccountAssets(extractedInfo: ExtractedAttackInfo): void {
    extractedInfo.indicators?.user_accounts?.forEach((account, index) => {
      const id = `indicator-account-${index}`;
      const displayName = account.domain ? `${account.domain}\\${account.username}` : account.username;
      
      this.nodes.push({
        id,
        type: 'attack-asset',
        spec_version: '2.1',
        name: displayName,
        description: account.description,
        role: 'User Account',
        asset_type: 'user',
        indicator_type: 'user-account',
        indicator_value: account.username,
        username: account.username,
        account_domain: account.domain,
        account_type: account.account_type,
        compromised: account.compromised,
        source_snippet: account.source_snippet || '',
        confidence: account.confidence || 'medium',
      });
      
      console.log(`Created user account asset: ${displayName} (${account.compromised ? 'compromised' : 'clean'})`);
      
      this.connectIndicatorToTechniques(account.used_by || [], id, 'Uses');
    });
  }

  private createRegistryKeyAssets(extractedInfo: ExtractedAttackInfo): void {
    extractedInfo.indicators?.registry_keys?.forEach((regKey, index) => {
      const id = `indicator-registry-${index}`;
      const keyPath = regKey.key_path || 'Unknown Registry Key';
      const displayName = regKey.value_name ? `${keyPath}\\${regKey.value_name}` : keyPath;
      
      this.nodes.push({
        id,
        type: 'attack-asset',
        spec_version: '2.1',
        name: displayName && displayName.length > 60 ? displayName.substring(0, 57) + '...' : displayName || 'Registry Key',
        description: regKey.description || 'Registry key modification',
        role: 'System Configuration',
        asset_type: 'system',
        indicator_type: 'registry-key',
        indicator_value: keyPath,
        registry_hive: regKey.hive,
        registry_key_path: keyPath,
        registry_value_name: regKey.value_name,
        registry_value_data: regKey.value_data,
        source_snippet: regKey.source_snippet || '',
        confidence: regKey.confidence || 'medium',
      });
      
      console.log(`Created registry key asset: ${displayName}`);
      
      this.connectIndicatorToTechniques(regKey.modified_by || [], id, 'Modifies');
    });
  }

  private createNetworkPortAssets(extractedInfo: ExtractedAttackInfo): void {
    extractedInfo.indicators?.network_ports?.forEach((port, index) => {
      const id = `indicator-port-${index}`;
      const protocol = port.protocol || 'tcp';
      const portNumber = port.port_number || 'Unknown';
      const displayName = `${protocol.toUpperCase()}/${portNumber}${port.service ? ` (${port.service})` : ''}`;
      
      this.nodes.push({
        id,
        type: 'attack-asset',
        spec_version: '2.1',
        name: displayName,
        description: port.description || `Network port ${portNumber}`,
        role: 'Network Port',
        asset_type: 'network',
        indicator_type: 'network-port',
        indicator_value: (port.port_number || 'Unknown').toString(),
        port_number: port.port_number,
        port_protocol: port.protocol,
        port_service: port.service,
        port_state: port.state,
        source_snippet: port.source_snippet || '',
        confidence: port.confidence || 'medium',
      });
      
      console.log(`Created network port asset: ${displayName} (${port.state || 'unknown state'})`);
      
      this.connectIndicatorToTechniques(port.used_by || [], id, 'Uses port');
    });
  }

  private connectIndicatorToTechniques(techniqueIds: string[], indicatorId: string, label: string): void {
    techniqueIds.forEach((techniqueId: string) => {
      const actionNode = this.nodes.find(n => 
        n.type === 'attack-action' && 
        (n.technique_id === techniqueId || n.name?.includes(techniqueId))
      );
      if (actionNode) {
        this.edges.push({
          id: uuidv4(),
          source: actionNode.id,
          target: indicatorId,
          label
        });
        console.log(`✅ Connected: Action "${actionNode.name}" to indicator via ${label}`);
      } else {
        console.log(`❌ No action found with technique ID: ${techniqueId} for indicator`);
      }
    });
  }

  private connectHashToFiles(hash: any, hashId: string): void {
    hash.associated_files?.forEach((fileName: string) => {
      const fileNode = this.nodes.find(n => n.type === 'file' && n.name === fileName);
      if (fileNode) {
        this.edges.push({
          id: uuidv4(),
          source: hashId,
          target: fileNode.id,
          label: 'Hash of'
        });
        console.log(`Hash "${hash.value.substring(0, 8)}..." is hash of file "${fileName}"`);
      }
    });
  }

  private createConditionNodes(extractedInfo: ExtractedAttackInfo): void {
    extractedInfo.conditions?.forEach((condition, index) => {
      const id = `condition-${index}`;
      
      if (condition.operator) {
        this.nodes.push({
          id,
          type: 'attack-operator',
          spec_version: '2.1',
          name: condition.name || `Operator ${index + 1}`,
          operator: condition.operator,
        });
      } else {
        this.nodes.push({
          id,
          type: 'attack-condition',
          spec_version: '2.1',
          name: condition.name || `Condition ${index + 1}`,
          description: condition.description,
          pattern: condition.pattern,
          pattern_type: 'sigma',
          context: condition.context,
          source_snippet: condition.source_snippet || '',
          confidence: condition.confidence || 'medium',
        });
      }

      this.connectConditionToActions(condition, id);
    });
  }

  private connectConditionToActions(condition: any, conditionId: string): void {
    const targetActionIds: string[] = [];
    
    if (!condition.enables_actions || condition.enables_actions.length === 0) {
      console.warn(`⚠️  Condition "${condition.name}" missing enables_actions field - this indicates a prompt compliance issue`);
    }
    
    if (condition.enables_actions && condition.enables_actions.length > 0) {
      condition.enables_actions.forEach((enabledAction: string) => {
        const enabledActionKey = enabledAction.toLowerCase().trim();
        let foundMatch = false;
        
        this.nodes.forEach(node => {
          if (node.type === 'attack-action' && !targetActionIds.includes(node.id)) {
            const exactTechniqueMatch = node.technique_id && 
              node.technique_id.toLowerCase() === enabledActionKey;
            
            const techniqueInText = enabledActionKey.startsWith('t1') && (
              (node.name && node.name.toLowerCase().includes(enabledActionKey)) ||
              (node.description && node.description.toLowerCase().includes(enabledActionKey))
            );
            
            const nameMatch = !enabledActionKey.startsWith('t1') && node.name && 
              (node.name.toLowerCase().includes(enabledActionKey) || 
               enabledActionKey.includes(node.name.toLowerCase().split(':')[0]));
            
            if (exactTechniqueMatch || techniqueInText || nameMatch) {
              targetActionIds.push(node.id);
              foundMatch = true;
              console.log(`✅ Condition "${condition.name}" enables action: ${node.name} (${node.id})`);
            }
          }
        });
        
        if (!foundMatch) {
          console.warn(`⚠️  No exact match found for technique "${enabledAction}" in condition "${condition.name}"`);
        }
      });
    }
    
    // Create edges for all identified relationships
    targetActionIds.forEach(targetActionId => {
      this.edges.push({
        id: uuidv4(),
        source: conditionId,
        target: targetActionId,
        label: condition.operator ? 'Enables' : 'Required for',
      });
    });
    
    // Handle success/failure branching
    this.handleConditionBranching(condition, conditionId);
  }

  private handleConditionBranching(condition: any, conditionId: string): void {
    if (condition.on_success && condition.on_success.length > 0) {
      condition.on_success.forEach((successTechniqueId: string) => {
        const successAction = this.nodes.find(n => 
          n.type === 'attack-action' && n.technique_id === successTechniqueId
        );
        if (successAction) {
          this.edges.push({
            id: uuidv4(),
            source: conditionId,
            target: successAction.id,
            label: 'On Success'
          });
          console.log(`Condition "${condition.name}" leads to ${successAction.name} on success`);
        }
      });
    }
    
    if (condition.on_failure && condition.on_failure.length > 0) {
      condition.on_failure.forEach((failureTechniqueId: string) => {
        const failureAction = this.nodes.find(n => 
          n.type === 'attack-action' && n.technique_id === failureTechniqueId
        );
        if (failureAction) {
          this.edges.push({
            id: uuidv4(),
            source: conditionId,
            target: failureAction.id,
            label: 'On Failure'
          });
          console.log(`Condition "${condition.name}" leads to ${failureAction.name} on failure`);
        }
      });
    }
  }

  private createInfrastructureNodes(extractedInfo: ExtractedAttackInfo): void {
    console.log('=== Creating Infrastructure Nodes ===');
    extractedInfo.infrastructure?.forEach((infra, index) => {
      const id = `infrastructure-${index}`;
      
      this.nodes.push({
        id,
        type: 'infrastructure',
        spec_version: '2.1',
        name: infra.name,
        description: infra.description,
        infrastructure_types: [infra.type || 'server'],
        source_snippet: infra.source_snippet || '',
        confidence: infra.confidence || 'medium',
      });
      
      console.log(`Created infrastructure node: ${infra.name} (${infra.type})`);
      
      this.connectInfrastructureToActions(infra, id);
    });
  }

  private connectInfrastructureToActions(infra: any, infraId: string): void {
    infra.used_by?.forEach((techniqueId: string) => {
      const actionNode = this.nodes.find(n => n.type === 'attack-action' && n.technique_id === techniqueId);
      if (actionNode) {
        this.edges.push({
          id: uuidv4(),
          source: actionNode.id,
          target: infraId,
          label: 'Uses'
        });
        console.log(`✅ Connected: Action "${actionNode.name}" uses infrastructure "${infra.name}"`);
      } else {
        console.log(`❌ No action found with technique ID: ${techniqueId} for infrastructure "${infra.name}"`);
      }
    });
  }

  private connectTactics(createdTactics: any[], extractedInfo: ExtractedAttackInfo): void {
    console.log('=== Creating Inter-Tactic Connections ===');
    for (let i = 0; i < createdTactics.length - 1; i++) {
      const currentTactic = createdTactics[i];
      const nextTactic = createdTactics[i + 1];
      
      // Only create direct connections if there are no operators managing the flow
      const hasOperatorFlow = extractedInfo.operators && extractedInfo.operators.length > 0;
      
      if (!hasOperatorFlow) {
        this.edges.push({
          id: `${currentTactic.prefix}-to-${nextTactic.prefix}`,
          source: currentTactic.lastActionId,
          target: nextTactic.firstActionId,
          label: 'Followed by'
        });
        
        console.log(`Connected tactics: ${currentTactic.lastActionId} -> ${nextTactic.firstActionId}`);
      }
    }
  }

  
  private async shouldConnectSequentialActionsWithLLM(prevAction: any, currentAction: any, isFirstConnection: boolean): Promise<{ connect: boolean, relationshipType: string, confidence: number }> {
    // REMOVED: Client-side API usage - now using simple heuristic
    return this.shouldConnectSequentialActionsHeuristic(prevAction, currentAction, isFirstConnection);
    
    /*
    try {
      const result = await this.relationshipAnalyzer.analyzeSequentialConnection({
        prevAction: {
          name: prevAction.name || 'Unknown',
          description: prevAction.description || '',
          technique: prevAction.technique
        },
        currentAction: {
          name: currentAction.name || 'Unknown',
          description: currentAction.description || '',
          technique: currentAction.technique
        },
        isFirstConnection
      });
      
      return result;
    } catch (error) {
      console.warn('LLM sequential connection failed, using fallback:', error);
      return { connect: true, relationshipType: 'Followed by', confidence: 0.5 };
    }
    */
  }

  private shouldConnectSequentialActionsHeuristic(prevAction: any, currentAction: any, isFirstConnection: boolean): { connect: boolean, relationshipType: string, confidence: number } {
    // Simple heuristic fallback - connect sequential actions with medium confidence
    return { 
      connect: true, 
      relationshipType: 'Followed by', 
      confidence: 0.7 
    };
  }

  private logFinalStatistics(createdTactics: any[]): void {
    // Create summary of assets at risk
    const assetSummary = this.nodes
      .filter(node => node.type === 'attack-asset')
      .map(asset => ({
        name: asset.name,
        reputation: (asset as any).indicator_reputation || 'unknown',
        type: (asset as any).indicator_type || (asset as any).asset_type || 'system',
        affected_by_count: (asset as any).affected_by?.length || 0
      }));
      
    console.log('=== Asset Risk Summary ===');
    console.log('Assets by reputation:');
    ['malicious', 'suspicious', 'clean', 'unknown'].forEach(reputation => {
      const count = assetSummary.filter(a => a.reputation === reputation).length;
      if (count > 0) {
        console.log(`- ${reputation.toUpperCase()}: ${count} assets`);
        assetSummary
          .filter(a => a.reputation === reputation)
          .forEach(asset => {
            console.log(`  • ${asset.name} (${asset.type}) - targeted by ${asset.affected_by_count} action(s)`);
          });
      }
    });

    console.log('=== ATTACK FLOW CONVERSION COMPLETE ===');
    console.log('=== Final Node Statistics ===');
    console.log(`Total nodes created: ${this.nodes.length}`);
    console.log('Node breakdown:');
    console.log(`- Asset nodes: ${this.nodes.filter(n => n.type === 'attack-asset').length}`);
    console.log(`- Condition nodes: ${this.nodes.filter(n => n.type === 'attack-condition').length}`);
    console.log(`- Operator nodes: ${this.nodes.filter(n => n.type === 'attack-operator').length}`);
    console.log(`- Vulnerability nodes: ${this.nodes.filter(n => n.type === 'vulnerability').length}`);
    console.log(`- Tool nodes: ${this.nodes.filter(n => n.type === 'tool').length}`);
    console.log(`- Process nodes: ${this.nodes.filter(n => n.type === 'process').length}`);
    console.log(`- File nodes: ${this.nodes.filter(n => n.type === 'file').length}`);
    console.log(`- Infrastructure nodes: ${this.nodes.filter(n => n.type === 'infrastructure').length}`);
    
    // Show breakdown by tactic
    createdTactics.forEach(tactic => {
      console.log(`- ${tactic.key} nodes: ${tactic.count}`);
    });
    
    console.log(`Total edges created: ${this.edges.length}`);
    console.log('Edge breakdown:');
    const edgeTypes = this.edges.reduce((acc, edge) => {
      acc[edge.label] = (acc[edge.label] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
    Object.entries(edgeTypes).forEach(([label, count]) => {
      console.log(`- ${label}: ${count}`);
    });
  }
}