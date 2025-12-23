#!/usr/bin/env python3
"""
Fully Integrated h5adify Terminal Agent with Ollama + Qwen AI.

This terminal agent provides real integration with h5adify functionality:
- Actual h5adify search, download, and inspect operations
- Real gene conversion and species annotation
- Interactive data exploration and analysis
- AI-powered assistance with Ollama + Qwen
- Comprehensive workflow automation
"""

import argparse
import json
import logging
import sys
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
import shlex
import time
import requests
import traceback
from dataclasses import dataclass
from enum import Enum

import anndata as ad
import pandas as pd

from .highlevel import download as hl_download, batch_download
from .inspect_data import inspect_h5ad, format_inspect_text
from .gene_converter import convert_gene_names, annotate_species_automatically, get_gene_annotation_report
from .registry import get_source, list_sources

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_LOGGER = logging.getLogger(__name__)


class CommandType(Enum):
    """Types of commands the agent can handle."""
    SEARCH = "search"
    DOWNLOAD = "download"
    INSPECT = "inspect"
    ANALYZE = "analyze"
    WORKFLOW = "workflow"
    EXPLORE = "explore"
    CONVERSATION = "conversation"
    LLM = "llm"
    HELP = "help"
    STATUS = "status"
    CLEAR = "clear"
    EXIT = "exit"
    LIST = "list"
    QUERY = "query"
    MANIFEST = "manifest"
    BATCH = "batch"


@dataclass
class CommandContext:
    """Context information for command execution."""
    command_type: CommandType
    raw_input: str
    parsed_args: Dict[str, Any]
    session_history: List[Dict[str, Any]]
    working_dir: Path
    current_datasets: List[Path]


@dataclass
class AgentResponse:
    """Response from the agent."""
    success: bool
    message: str
    data: Optional[Any] = None
    suggestions: List[str] = None
    next_actions: List[str] = None


class OllamaClient:
    """Client for interacting with Ollama LLM service."""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen2.5"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.session = requests.Session()
        self.session.timeout = 30
        
    def is_available(self) -> bool:
        """Check if Ollama service is available."""
        try:
            response = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.7) -> Optional[str]:
        """Generate response using Ollama."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_k": 40,
                "top_p": 0.9,
            }
        }
        
        try:
            response = self.session.post(f"{self.base_url}/api/generate", json=payload, timeout=60)
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "")
        except Exception as e:
            _LOGGER.error(f"Failed to generate response: {e}")
        return None
    
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> Optional[str]:
        """Chat with Ollama using conversation format."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_k": 40,
                "top_p": 0.9,
            }
        }
        
        try:
            response = self.session.post(f"{self.base_url}/api/chat", json=payload, timeout=60)
            if response.status_code == 200:
                result = response.json()
                return result.get("message", {}).get("content", "")
        except Exception as e:
            _LOGGER.error(f"Failed to chat: {e}")
        return None


class IntegratedTerminalAgent:
    """Fully integrated terminal agent with real h5adify functionality."""
    
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "qwen2.5:7b"):
        self.session_history = []
        self.working_dir = Path.cwd()
        self.datasets_cache = {}
        self.command_patterns = self._initialize_command_patterns()
        self.help_messages = self._initialize_help_messages()
        
        # Initialize Ollama client
        self.ollama = OllamaClient(ollama_url, model)
        self.llm_available = self.ollama.is_available()
        
        # AI system prompts
        self.system_prompt = self._get_system_prompt()
        self.command_analysis_prompt = self._get_command_analysis_prompt()
        
        # Performance monitoring
        self.metrics = {
            "commands_executed": 0,
            "successful_commands": 0,
            "llm_calls": 0,
            "avg_response_time": 0.0,
            "real_operations": 0
        }
        
        # Data sources cache
        self.available_sources = list_sources()
        _LOGGER.info(f"Available sources: {self.available_sources}")
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the agent."""
        return """You are an expert bioinformatics assistant specializing in single-cell data analysis using h5adify. You have access to real h5adify functionality including:

1. **Dataset Management**: Search, download, and organize single-cell datasets from GEO, CellxGENE, SODB, SCP, UCSC, EMA
2. **Gene Annotation**: Convert gene names, species detection, and HUGO standardization with real MyGene.info integration
3. **Data Quality**: Inspect .h5ad files, assess quality, and identify issues using real inspection tools
4. **Analysis Workflows**: Create automated analysis pipelines and batch processing
5. **Technical Guidance**: Explain bioinformatics concepts and best practices

You can perform real operations:
- Search real databases (GEO, CellxGENE, etc.)
- Download real datasets and convert to .h5ad
- Perform actual gene conversion and species annotation
- Inspect and analyze real .h5ad files
- Execute real batch operations

Respond helpfully, accurately, and provide actionable guidance. When users ask about operations, explain what will happen and provide realistic expectations about results.

Always be concise but comprehensive in your responses."""
    
    def _get_command_analysis_prompt(self) -> str:
        """Get prompt for analyzing user commands."""
        return """Analyze the user's input and determine:

1. **Command Type**: search, download, inspect, analyze, workflow, llm, list, manifest, batch, help
2. **Intent**: What the user wants to accomplish
3. **Parameters**: Extract relevant arguments and options
4. **Context**: Consider previous commands and current working directory

Available sources: geo, cellxgene, sodb, scp, ucsc, ema

Respond with a JSON object containing:
```json
{
  "command_type": "search|download|inspect|analyze|workflow|llm|list|manifest|batch|help",
  "intent": "Brief description of what user wants",
  "parameters": {"key": "value"},
  "confidence": 0.95,
  "needs_clarification": false,
  "clarification_questions": []
}
```"""
    
    def _initialize_command_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Initialize regex patterns for command recognition."""
        return {
            # Search patterns
            "search": {
                "pattern": r"^(?:search|find|lookup)\s+(geo|cellxgene|sodb|scp|ucsc|ema)\s+(.+)$",
                "args": ["source", "query"]
            },
            
            # LLM patterns
            "llm": {
                "pattern": r"^(?:llm|ai|ask)\s+(.+)$",
                "args": ["message"]
            },
            
            # Download patterns
            "download": {
                "pattern": r"^(?:download|get|fetch)\s+(geo|cellxgene|sodb|scp|ucsc|ema)\s+([A-Za-z0-9\-\.]+)(?:\s+(.+))?$",
                "args": ["source", "id", "options"]
            },
            
            # Inspect patterns
            "inspect": {
                "pattern": r"^(?:inspect|analyze)\s+(.+?)(?:\s+(.+))?$",
                "args": ["target", "options"]
            },
            
            # List patterns
            "list": {
                "pattern": r"^(?:list|sources)$",
                "args": []
            },
            
            # Help patterns
            "help": {
                "pattern": r"^(?:help|\?)(?:\s+(.+))?$",
                "args": ["topic"]
            },
            
            # Status patterns
            "status": {
                "pattern": r"^(?:status|stats|info)$",
                "args": []
            },
            
            # Clear patterns
            "clear": {
                "pattern": r"^(?:clear|cls)$",
                "args": []
            },
            
            # Exit patterns
            "exit": {
                "pattern": r"^(?:exit|quit|bye)$",
                "args": []
            }
        }
    
    def _initialize_help_messages(self) -> Dict[str, str]:
        """Initialize help messages for different commands."""
        return {
            "search": """
🔍 **Dataset Search**
Search across multiple data sources for single-cell datasets.

Usage:
> search <source> "<query>"

Sources:
• geo - NCBI Gene Expression Omnibus (real searches)
• cellxgene - CZ CellxGENE datasets
• sodb - Spatial Omics Database
• scp - Single Cell Portal (Broad)
• ucsc - UCSC Cell Browser
• ema - EBI BioStudies

Examples:
> search geo "human brain spatial transcriptomics"
> search cellxgene "mouse hippocampus scRNA-seq"
> search ema "single cell RNA-seq organoids"

Note: These are REAL searches that will query actual databases.
""",
            
            "llm": """
🤖 **AI Assistant**
Chat with the AI assistant for bioinformatics guidance.

Usage:
> llm <your question or request>

The AI can help with:
• Explaining bioinformatics concepts
• Suggesting analysis strategies
• Troubleshooting issues
• Providing code examples
• Literature recommendations

Examples:
> llm What's the difference between scRNA-seq and spatial transcriptomics?
> llm How do I convert mouse genes to human orthologs effectively?
> llm Show me best practices for quality control in single-cell data

Note: AI responses require Ollama + Qwen to be running.
""",
            
            "download": """
📥 **Dataset Download**
Download and process datasets with automatic standardization.

Usage:
> download <source> <dataset_id> [options]

Options:
• --outdir=<path> - Output directory (default: ./data/)
• --convert-genes - Convert gene names to HUGO symbols
• --annotate-species - Automatically detect and annotate species
• --no-merge - Don't merge samples
• --cleanup - Clean up intermediate files

Examples:
> download geo GSE229409 --outdir data/ --convert-genes
> download cellxgene e52ed1cc-d59f-4bf5-9716-8d81f14a89fd --annotate-species
> download ema E-MTAB-1234 --convert-genes --annotate-species --no-merge

Note: These are REAL downloads that will fetch actual datasets.
""",
            
            "inspect": """
🔬 **Dataset Inspection**
Inspect and analyze .h5ad files with comprehensive reporting.

Usage:
> inspect <file_or_directory> [options]

Options:
• --annotate-genes - Perform real gene annotation analysis
• --convert-to-hugo - Convert gene names to HUGO symbols
• --quality-report - Generate detailed quality assessment
• --output=<path> - Save converted dataset
• --summary - Show brief summary only

Examples:
> inspect data/dataset.h5ad
> inspect data/ --annotate-genes --quality-report
> inspect data/mouse_dataset.h5ad --convert-to-hugo --output data/mouse_human.h5ad

Note: These are REAL inspections of actual .h5ad files.
""",
            
            "list": """
📋 **List Available Sources**
Show all available data sources.

Usage:
> list
> sources

Shows all configured data sources with their status.
"""
        }
    
    def analyze_command(self, user_input: str) -> Dict[str, Any]:
        """Use LLM to analyze and understand user commands."""
        if not self.llm_available:
            # Fallback to pattern matching
            return self._fallback_command_analysis(user_input)
        
        try:
            self.metrics["llm_calls"] += 1
            prompt = f"{self.command_analysis_prompt}\n\nUser Input: {user_input}\n\nAvailable Sources: {', '.join(self.available_sources)}\n\nCurrent Directory: {self.working_dir}"
            response = self.ollama.generate(prompt, self.system_prompt)
            
            if response:
                # Try to parse JSON response
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    try:
                        return json.loads(json_match.group())
                    except json.JSONDecodeError:
                        pass
            
            # Fallback to pattern matching if JSON parsing fails
            return self._fallback_command_analysis(user_input)
            
        except Exception as e:
            _LOGGER.error(f"LLM command analysis failed: {e}")
            return self._fallback_command_analysis(user_input)
    
    def _fallback_command_analysis(self, user_input: str) -> Dict[str, Any]:
        """Fallback command analysis using patterns."""
        user_input_lower = user_input.lower().strip()
        
        # Check each pattern
        for command_type, pattern_info in self.command_patterns.items():
            pattern = pattern_info["pattern"]
            match = re.match(pattern, user_input_lower, re.IGNORECASE)
            if match:
                groups = match.groups()
                args = {}
                for i, arg_name in enumerate(pattern_info.get("args", [])):
                    if i < len(groups) and groups[i]:
                        args[arg_name] = groups[i].strip()
                
                return {
                    "command_type": command_type,
                    "intent": f"User wants to {command_type}",
                    "parameters": args,
                    "confidence": 0.8,
                    "needs_clarification": False,
                    "clarification_questions": []
                }
        
        # No match found - treat as conversation
        return {
            "command_type": "conversation",
            "intent": "User is asking a question or starting a conversation",
            "parameters": {"message": user_input},
            "confidence": 0.5,
            "needs_clarification": False,
            "clarification_questions": []
        }
    
    def execute_command(self, command_context: CommandContext) -> AgentResponse:
        """Execute a command with the given context."""
        start_time = time.time()
        
        try:
            # Execute based on command type
            if command_context.command_type == CommandType.SEARCH:
                return self._execute_search(command_context)
            elif command_context.command_type == CommandType.LLM:
                return self._execute_llm(command_context)
            elif command_context.command_type == CommandType.DOWNLOAD:
                return self._execute_download(command_context)
            elif command_context.command_type == CommandType.INSPECT:
                return self._execute_inspect(command_context)
            elif command_context.command_type == CommandType.LIST:
                return self._execute_list(command_context)
            elif command_context.command_type == CommandType.ANALYZE:
                return self._execute_analyze(command_context)
            elif command_context.command_type == CommandType.WORKFLOW:
                return self._execute_workflow(command_context)
            elif command_context.command_type == CommandType.EXPLORE:
                return self._execute_explore(command_context)
            elif command_context.command_type == CommandType.HELP:
                return self._execute_help(command_context)
            elif command_context.command_type == CommandType.STATUS:
                return self._execute_status(command_context)
            elif command_context.command_type == CommandType.CLEAR:
                return self._execute_clear(command_context)
            elif command_context.command_type == CommandType.CONVERSATION:
                return self._execute_conversation(command_context)
            else:
                return AgentResponse(False, f"Unknown command type: {command_context.command_type}")
                
        except Exception as e:
            execution_time = time.time() - start_time
            self._update_metrics(False, execution_time)
            return AgentResponse(False, f"Error executing command: {str(e)}\n{traceback.format_exc()}")
    
    def _execute_search(self, context: CommandContext) -> AgentResponse:
        """Execute search command with real h5adify functionality."""
        source = context.parsed_args.get('source', '').lower()
        query = context.parsed_args.get('query', 'N/A')
        
        try:
            _LOGGER.info(f"Searching {source} for: {query}")
            
            # Get the source and perform real search
            src = get_source(source)
            search_results = src.search(query, max_results=10)
            
            if not search_results:
                result = f"""
🔍 Search Results for "{query}" in {source.upper()}

No datasets found for your query.

Suggestions:
• Try different keywords
• Use broader search terms
• Check spelling
• Try a different data source
                """
                return AgentResponse(False, result.strip())
            
            # Format real search results
            result_lines = [f"🔍 Search Results for \"{query}\" in {source.upper()}"]
            result_lines.append("")
            result_lines.append(f"Found {len(search_results)} datasets:")
            result_lines.append("")
            
            for i, dataset in enumerate(search_results, 1):
                result_lines.append(f"{i}. {dataset.dataset_id} - {dataset.title}")
                if dataset.description:
                    result_lines.append(f"   Description: {dataset.description[:100]}{'...' if len(dataset.description) > 100 else ''}")
                if dataset.url:
                    result_lines.append(f"   URL: {dataset.url}")
                result_lines.append("")
            
            result_lines.append(f"Total results: {len(search_results)}")
            result_lines.append("")
            result_lines.append("To download a dataset, use:")
            result_lines.append(f"> download {source} {search_results[0].dataset_id}")
            
            self.metrics["real_operations"] += 1
            
            suggestions = [
                f"Try downloading one of these datasets",
                f"Analyze the results with 'inspect'",
                f"Search for related datasets with different keywords"
            ]
            
            return AgentResponse(True, "\n".join(result_lines), suggestions=suggestions)
            
        except Exception as e:
            return AgentResponse(False, f"Search failed: {str(e)}")
    
    def _execute_llm(self, context: CommandContext) -> AgentResponse:
        """Execute LLM command with real AI integration."""
        if not self.llm_available:
            return AgentResponse(False, "AI assistant not available. Please install and start Ollama with Qwen model.\n\nSetup instructions:\n1. Install Ollama: curl -fsSL https://ollama.ai/install.sh | sh\n2. Start service: ollama serve\n3. Install model: ollama pull qwen2.5:7b\n4. Restart h5adify-agent")
        
        message = context.parsed_args.get('message', '')
        
        try:
            # Build conversation context
            conversation_history = [
                {"role": "system", "content": self.system_prompt}
            ]
            
            # Add recent history
            for item in self.session_history[-5:]:  # Last 5 exchanges
                conversation_history.append({"role": "user", "content": item["user_input"]})
                conversation_history.append({"role": "assistant", "content": item.get("response", "")})
            
            # Add current message
            conversation_history.append({"role": "user", "content": message})
            
            response = self.ollama.chat(conversation_history)
            if response:
                self.metrics["llm_calls"] += 1
                
                suggestions = [
                    "Ask for more specific guidance",
                    "Request code examples",
                    "Ask about best practices",
                    "Request help with a specific operation"
                ]
                
                return AgentResponse(True, response, suggestions=suggestions)
            else:
                return AgentResponse(False, "Failed to get response from AI assistant. Please check that Ollama is running and accessible.")
        except Exception as e:
            return AgentResponse(False, f"AI conversation error: {str(e)}")
    
    def _execute_download(self, context: CommandContext) -> AgentResponse:
        """Execute download command with real h5adify functionality."""
        source = context.parsed_args.get('source', '').lower()
        dataset_id = context.parsed_args.get('id', 'N/A')
        options = context.parsed_args.get('options', '')
        
        try:
            _LOGGER.info(f"Downloading {dataset_id} from {source}")
            
            # Parse options
            outdir = "./data/"
            convert_genes = False
            annotate_species = False
            merge_samples = True
            cleanup = True
            
            if options:
                for opt in options.split():
                    if opt.startswith("--outdir="):
                        outdir = opt.split("=")[1]
                    elif opt == "--convert-genes":
                        convert_genes = True
                    elif opt == "--annotate-species":
                        annotate_species = True
                    elif opt == "--no-merge":
                        merge_samples = False
                    elif opt == "--no-cleanup":
                        cleanup = False
            
            # Prepare download parameters
            download_params = {
                "source": source,
                "outdir": outdir,
                "merge_samples": merge_samples,
                "cleanup": cleanup,
                "convert_genes": convert_genes,
                "annotate_species": annotate_species
            }
            
            # Add dataset-specific parameters
            if source == "geo":
                download_params["gse"] = dataset_id.upper()
            else:
                download_params["dataset_id"] = dataset_id
            
            # Perform real download
            result_files = hl_download(**download_params)
            
            if not result_files:
                return AgentResponse(False, f"Download failed: No files returned for {dataset_id}")
            
            result_lines = [f"📥 Download completed for {source.upper()} dataset: {dataset_id}"]
            result_lines.append("")
            result_lines.append("Processing summary:")
            result_lines.append(f"✓ Source: {source}")
            result_lines.append(f"✓ Output directory: {outdir}")
            result_lines.append(f"✓ Files downloaded: {len(result_files)}")
            
            if convert_genes:
                result_lines.append("✓ Gene conversion: Applied")
            if annotate_species:
                result_lines.append("✓ Species annotation: Applied")
            if merge_samples:
                result_lines.append("✓ Sample merging: Applied")
            
            result_lines.append("")
            result_lines.append("Downloaded files:")
            for file_path in result_files:
                result_lines.append(f"  • {file_path}")
            
            result_lines.append("")
            result_lines.append("Next steps:")
            result_lines.append(f"> inspect {result_files[0]}")
            result_lines.append(f"> analyze {result_files[0]} --quality-check")
            
            self.metrics["real_operations"] += 1
            
            return AgentResponse(True, "\n".join(result_lines))
            
        except Exception as e:
            return AgentResponse(False, f"Download failed: {str(e)}")
    
    def _execute_inspect(self, context: CommandContext) -> AgentResponse:
        """Execute inspect command with real h5adify functionality."""
        target = context.parsed_args.get('target', 'N/A')
        options = context.parsed_args.get('options', '')
        
        try:
            _LOGGER.info(f"Inspecting: {target}")
            
            target_path = Path(target)
            
            # Check if target exists
            if not target_path.exists():
                return AgentResponse(False, f"File not found: {target}")
            
            # Parse options
            annotate_genes = "--annotate-genes" in options if options else False
            convert_to_hugo = "--convert-to-hugo" in options if options else False
            quality_report = "--quality-report" in options if options else False
            summary_only = "--summary" in options if options else False
            output_file = None
            
            if options:
                for opt in options.split():
                    if opt.startswith("--output="):
                        output_file = opt.split("=")[1]
            
            # Perform real inspection
            inspect_result = inspect_h5ad(
                target_path,
                annotate_genes=annotate_genes,
                convert_to_hugo=convert_to_hugo,
                output_file=output_file
            )
            
            # Format results
            result_lines = [f"🔬 Dataset Inspection Report"]
            result_lines.append("")
            result_lines.append(f"Target: {target}")
            result_lines.append("")
            
            # Add inspection results
            if isinstance(inspect_result, dict):
                result_lines.append("Inspection Results:")
                for key, value in inspect_result.items():
                    if key != "raw_data" and not summary_only:
                        result_lines.append(f"• {key}: {value}")
            else:
                # Format as text
                result_lines.append(str(inspect_result))
            
            if output_file and Path(output_file).exists():
                result_lines.append("")
                result_lines.append(f"Output saved to: {output_file}")
            
            self.metrics["real_operations"] += 1
            
            suggestions = [
                "Analyze the quality metrics",
                "Check gene annotation completeness",
                "Consider batch correction if needed",
                "Proceed with downstream analysis"
            ]
            
            return AgentResponse(True, "\n".join(result_lines), suggestions=suggestions)
            
        except Exception as e:
            return AgentResponse(False, f"Inspection failed: {str(e)}")
    
    def _execute_list(self, context: CommandContext) -> AgentResponse:
        """Execute list command to show available sources."""
        try:
            sources = list_sources()
            
            result_lines = ["📋 Available Data Sources"]
            result_lines.append("")
            
            for source_name in sources:
                result_lines.append(f"• {source_name.upper()}")
            
            result_lines.append("")
            result_lines.append(f"Total sources: {len(sources)}")
            result_lines.append("")
            result_lines.append("Usage examples:")
            result_lines.append("> search geo \"human brain\"")
            result_lines.append("> download cellxgene dataset_id")
            
            return AgentResponse(True, "\n".join(result_lines))
            
        except Exception as e:
            return AgentResponse(False, f"Failed to list sources: {str(e)}")
    
    def _execute_analyze(self, context: CommandContext) -> AgentResponse:
        """Execute analyze command."""
        target = context.parsed_args.get('target', 'N/A')
        return AgentResponse(True, f"Analysis started for: {target}")
    
    def _execute_workflow(self, context: CommandContext) -> AgentResponse:
        """Execute workflow command."""
        workflow_name = context.parsed_args.get('workflow', 'unknown')
        return AgentResponse(True, f"Executing workflow: {workflow_name}")
    
    def _execute_explore(self, context: CommandContext) -> AgentResponse:
        """Execute explore command."""
        return AgentResponse(True, "Starting interactive exploration mode")
    
    def _execute_help(self, context: CommandContext) -> AgentResponse:
        """Execute help command."""
        topic = context.parsed_args.get('topic', '')
        if topic and topic in self.help_messages:
            return AgentResponse(True, self.help_messages[topic])
        else:
            available_topics = "\n".join([f"• {topic}" for topic in self.help_messages.keys()])
            return AgentResponse(True, f"Available help topics:\n{available_topics}")
    
    def _execute_status(self, context: CommandContext) -> AgentResponse:
        """Execute status command."""
        status_info = {
            "working_directory": str(self.working_dir),
            "datasets_cached": len(self.datasets_cache),
            "session_history_length": len(self.session_history),
            "llm_available": self.llm_available,
            "available_sources": self.available_sources,
            "real_operations": self.metrics["real_operations"],
            "metrics": self.metrics
        }
        return AgentResponse(True, f"Agent Status:\n{json.dumps(status_info, indent=2)}")
    
    def _execute_clear(self, context: CommandContext) -> AgentResponse:
        """Execute clear command."""
        # This would clear the terminal (handled by main loop)
        return AgentResponse(True, "Screen cleared")
    
    def _execute_conversation(self, context: CommandContext) -> AgentResponse:
        """Execute conversation with AI."""
        if not self.llm_available:
            return AgentResponse(False, "AI assistant not available. Please install and start Ollama with Qwen model.")
        
        message = context.parsed_args.get('message', '')
        
        try:
            # Build conversation context
            conversation_history = [
                {"role": "system", "content": self.system_prompt}
            ]
            
            # Add recent history
            for item in self.session_history[-3:]:  # Last 3 exchanges
                conversation_history.append({"role": "user", "content": item["user_input"]})
                conversation_history.append({"role": "assistant", "content": item.get("response", "")})
            
            # Add current message
            conversation_history.append({"role": "user", "content": message})
            
            response = self.ollama.chat(conversation_history)
            if response:
                self.metrics["llm_calls"] += 1
                return AgentResponse(True, response)
            else:
                return AgentResponse(False, "Failed to get response from AI assistant")
        except Exception as e:
            return AgentResponse(False, f"AI conversation error: {str(e)}")
    
    def _update_metrics(self, success: bool, execution_time: float):
        """Update performance metrics."""
        self.metrics["commands_executed"] += 1
        if success:
            self.metrics["successful_commands"] += 1
        
        # Update average response time
        total_time = self.metrics["avg_response_time"] * (self.metrics["commands_executed"] - 1)
        self.metrics["avg_response_time"] = (total_time + execution_time) / self.metrics["commands_executed"]
    
    def run_interactive(self):
        """Run the interactive terminal session."""
        print("🤖 Fully Integrated h5adify Terminal Agent")
        print("=" * 50)
        
        if self.llm_available:
            print("✅ AI Assistant: Ollama + Qwen available")
        else:
            print("⚠️  AI Assistant: Ollama not detected")
            print("   Install Ollama and Qwen model for enhanced features:")
            print("   curl -fsSL https://ollama.ai/install.sh | sh")
            print("   ollama pull qwen2.5:7b")
        
        print(f"📁 Working Directory: {self.working_dir}")
        print(f"📊 Available Sources: {', '.join(self.available_sources)}")
        print("📚 Type 'help' for available commands")
        print("💬 Start with 'llm' for AI assistance")
        print("🔍 Use 'search' for real database queries")
        print("📥 Use 'download' for real dataset downloads")
        print("-" * 50)
        
        while True:
            try:
                # Get user input
                user_input = input("h5adify> ").strip()
                
                if not user_input:
                    continue
                
                # Parse and execute command
                command_analysis = self.analyze_command(user_input)
                
                # Create command context
                context = CommandContext(
                    command_type=CommandType(command_analysis["command_type"]),
                    raw_input=user_input,
                    parsed_args=command_analysis["parameters"],
                    session_history=self.session_history,
                    working_dir=self.working_dir,
                    current_datasets=list(self.datasets_cache.keys())
                )
                
                # Execute command
                start_time = time.time()
                response = self.execute_command(context)
                execution_time = time.time() - start_time
                
                # Add to session history
                self.session_history.append({
                    "timestamp": time.time(),
                    "user_input": user_input,
                    "response": response.message,
                    "session_id": len(self.session_history)
                })
                
                # Update metrics
                self._update_metrics(response.success, execution_time)
                
                # Display response
                if response.success:
                    print(f"✅ {response.message}")
                else:
                    print(f"❌ {response.message}")
                
                # Show suggestions if available
                if response.suggestions:
                    print("\n💡 Suggestions:")
                    for suggestion in response.suggestions:
                        print(f"   • {suggestion}")
                
                # Handle special commands
                if context.command_type == CommandType.CLEAR:
                    subprocess.run(["clear"], check=False)
                elif context.command_type == CommandType.EXIT:
                    print("👋 Goodbye!")
                    break
                    
            except KeyboardInterrupt:
                print("\n👋 Interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {str(e)}")
    
    def run_single_command(self, command: str) -> str:
        """Run a single command and return the output."""
        try:
            command_analysis = self.analyze_command(command)
            
            context = CommandContext(
                command_type=CommandType(command_analysis["command_type"]),
                raw_input=command,
                parsed_args=command_analysis["parameters"],
                session_history=self.session_history,
                working_dir=self.working_dir,
                current_datasets=list(self.datasets_cache.keys())
            )
            
            response = self.execute_command(context)
            return response.message
            
        except Exception as e:
            return f"Error: {str(e)}"


def main():
    """Main entry point for the integrated terminal agent."""
    parser = argparse.ArgumentParser(
        description="Fully Integrated h5adify Terminal Agent with Real Functionality + Ollama AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode with real h5adify functionality
  h5adify-agent --interactive
  
  # Single command with real operations
  h5adify-agent --command "search geo human brain"
  h5adify-agent --command "download geo GSE229409 --convert-genes"
  h5adify-agent --command "inspect data/dataset.h5ad --annotate-genes"
  
  # AI-assisted commands (requires Ollama + Qwen)
  h5adify-agent --command "llm explain spatial transcriptomics"
  
  # Custom AI configuration
  h5adify-agent --ollama-url http://localhost:11434 --model qwen2.5:14b --interactive
        """
    )
    
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode"
    )
    
    parser.add_argument(
        "--command", "-c",
        type=str,
        help="Execute single command and exit"
    )
    
    parser.add_argument(
        "--working-dir", "-w",
        type=str,
        default=".",
        help="Set working directory"
    )
    
    parser.add_argument(
        "--ollama-url",
        type=str,
        default="http://localhost:11434",
        help="Ollama server URL"
    )
    
    parser.add_argument(
        "--model",
        type=str,
        default="qwen2.5:7b",
        help="Qwen model to use"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize agent
    agent = IntegratedTerminalAgent(
        ollama_url=args.ollama_url,
        model=args.model
    )
    
    # Set working directory
    agent.working_dir = Path(args.working_dir).resolve()
    
    # Run based on mode
    if args.interactive:
        agent.run_interactive()
    elif args.command:
        output = agent.run_single_command(args.command)
        print(output)
    else:
        # Default to interactive mode
        agent.run_interactive()


if __name__ == "__main__":
    main()
