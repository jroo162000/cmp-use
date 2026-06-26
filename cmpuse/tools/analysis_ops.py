"""
Scientific and Technical Analysis Tool - Advanced computational capabilities
Provides mathematical, statistical, code, and data analysis for AVA
"""

from __future__ import annotations
from typing import Any, Dict
from ..tool_registry import Tool, register
import os


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    operation = args.get("operation", "analyze")
    return {"preview": f"Scientific Analysis: {operation}", "args": args}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    """Execute scientific and technical analysis operations"""
    operation = args.get("operation", "analyze")

    if dry_run:
        return {"status": "ok", "message": f"Would perform {operation} analysis"}

    # Mathematical calculations
    if operation == "calculate":
        return _calculate(args)

    # Statistical analysis
    elif operation == "statistics":
        return _statistics(args)

    # Data analysis
    elif operation == "data_analysis":
        return _data_analysis(args)

    # Code analysis
    elif operation == "code_analysis":
        return _code_analysis(args)

    # Scientific computation
    elif operation == "scientific":
        return _scientific_compute(args)

    # Research assistance
    elif operation == "research":
        return _research_assist(args)

    # General analysis using GPT-5.2 Pro
    elif operation == "analyze":
        return _ai_analysis(args)

    else:
        return {"status": "error", "message": f"Unknown operation: {operation}"}


def _calculate(args: Dict[str, Any]) -> Dict[str, Any]:
    """Advanced mathematical calculations"""
    try:
        expression = args.get("expression", "")

        if not expression:
            return {"status": "error", "message": "No expression provided"}

        # Try to use sympy for symbolic math if available
        try:
            import sympy as sp
            # Parse and evaluate expression
            result = sp.sympify(expression)
            simplified = sp.simplify(result)
            numeric = float(simplified.evalf()) if simplified.is_number else None

            return {
                "status": "ok",
                "expression": str(expression),
                "simplified": str(simplified),
                "numeric_value": numeric,
                "latex": sp.latex(simplified) if hasattr(sp, 'latex') else None
            }
        except ImportError:
            # Fallback to basic Python eval (safe subset)
            import math
            import numpy as np

            # Create safe namespace
            safe_dict = {
                'abs': abs, 'round': round, 'min': min, 'max': max,
                'sum': sum, 'pow': pow, 'sqrt': math.sqrt,
                'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
                'log': math.log, 'log10': math.log10, 'exp': math.exp,
                'pi': math.pi, 'e': math.e,
                'np': np, 'math': math
            }

            result = eval(expression, {"__builtins__": {}}, safe_dict)

            return {
                "status": "ok",
                "expression": str(expression),
                "result": float(result),
                "type": type(result).__name__
            }

    except Exception as e:
        return {"status": "error", "message": f"Calculation error: {str(e)}"}


def _statistics(args: Dict[str, Any]) -> Dict[str, Any]:
    """Statistical analysis of datasets"""
    try:
        data = args.get("data", [])

        if not data:
            return {"status": "error", "message": "No data provided"}

        import numpy as np
        from scipy import stats as scipy_stats

        # Convert to numpy array
        arr = np.array(data, dtype=float)

        # Calculate comprehensive statistics
        results = {
            "status": "ok",
            "count": len(arr),
            "mean": float(np.mean(arr)),
            "median": float(np.median(arr)),
            "mode": float(scipy_stats.mode(arr, keepdims=True)[0][0]) if len(arr) > 0 else None,
            "std_dev": float(np.std(arr)),
            "variance": float(np.var(arr)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "range": float(np.max(arr) - np.min(arr)),
            "q1": float(np.percentile(arr, 25)),
            "q3": float(np.percentile(arr, 75)),
            "iqr": float(np.percentile(arr, 75) - np.percentile(arr, 25)),
            "skewness": float(scipy_stats.skew(arr)),
            "kurtosis": float(scipy_stats.kurtosis(arr))
        }

        return results

    except ImportError:
        # Fallback to basic statistics
        try:
            data = args.get("data", [])
            arr = [float(x) for x in data]

            mean = sum(arr) / len(arr)
            variance = sum((x - mean) ** 2 for x in arr) / len(arr)
            std_dev = variance ** 0.5

            sorted_arr = sorted(arr)
            median = sorted_arr[len(sorted_arr) // 2]

            return {
                "status": "ok",
                "count": len(arr),
                "mean": mean,
                "median": median,
                "std_dev": std_dev,
                "variance": variance,
                "min": min(arr),
                "max": max(arr),
                "range": max(arr) - min(arr)
            }
        except Exception as e:
            return {"status": "error", "message": f"Statistics error: {str(e)}"}

    except Exception as e:
        return {"status": "error", "message": f"Statistics error: {str(e)}"}


def _data_analysis(args: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze datasets and patterns"""
    try:
        data = args.get("data", [])
        analysis_type = args.get("analysis_type", "summary")

        if not data:
            return {"status": "error", "message": "No data provided"}

        import numpy as np

        if analysis_type == "summary":
            # Comprehensive data summary
            arr = np.array(data)

            return {
                "status": "ok",
                "shape": arr.shape,
                "dtype": str(arr.dtype),
                "size": int(arr.size),
                "dimensions": int(arr.ndim),
                "memory_usage": int(arr.nbytes),
                "unique_values": int(len(np.unique(arr))),
                "has_nan": bool(np.isnan(arr).any()) if np.issubdtype(arr.dtype, np.number) else False,
                "has_inf": bool(np.isinf(arr).any()) if np.issubdtype(arr.dtype, np.number) else False
            }

        elif analysis_type == "correlation":
            # Correlation analysis for 2D data
            arr = np.array(data)
            if arr.ndim == 2:
                corr_matrix = np.corrcoef(arr.T)
                return {
                    "status": "ok",
                    "correlation_matrix": corr_matrix.tolist(),
                    "analysis": "Correlation matrix computed"
                }
            else:
                return {"status": "error", "message": "Correlation requires 2D data"}

        elif analysis_type == "trend":
            # Trend analysis
            arr = np.array(data)
            x = np.arange(len(arr))
            coeffs = np.polyfit(x, arr, 1)

            return {
                "status": "ok",
                "slope": float(coeffs[0]),
                "intercept": float(coeffs[1]),
                "trend": "increasing" if coeffs[0] > 0 else "decreasing" if coeffs[0] < 0 else "flat"
            }

        else:
            return {"status": "error", "message": f"Unknown analysis type: {analysis_type}"}

    except Exception as e:
        return {"status": "error", "message": f"Data analysis error: {str(e)}"}


def _code_analysis(args: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze code complexity, quality, and patterns"""
    try:
        code = args.get("code", "")
        language = args.get("language", "python")

        if not code:
            return {"status": "error", "message": "No code provided"}

        if language.lower() == "python":
            # Python code analysis
            import ast

            try:
                tree = ast.parse(code)

                # Count various elements
                functions = sum(1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
                classes = sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
                imports = sum(1 for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)))
                loops = sum(1 for node in ast.walk(tree) if isinstance(node, (ast.For, ast.While)))
                conditionals = sum(1 for node in ast.walk(tree) if isinstance(node, ast.If))

                # Calculate complexity metrics
                lines = code.split('\n')
                loc = len([l for l in lines if l.strip() and not l.strip().startswith('#')])
                comments = len([l for l in lines if l.strip().startswith('#')])

                return {
                    "status": "ok",
                    "language": "Python",
                    "valid_syntax": True,
                    "functions": functions,
                    "classes": classes,
                    "imports": imports,
                    "loops": loops,
                    "conditionals": conditionals,
                    "lines_of_code": loc,
                    "comment_lines": comments,
                    "comment_ratio": round(comments / max(loc, 1), 2),
                    "cyclomatic_complexity": conditionals + loops + 1
                }

            except SyntaxError as e:
                return {
                    "status": "error",
                    "message": f"Syntax error: {str(e)}",
                    "line": e.lineno,
                    "offset": e.offset
                }
        else:
            # Generic code analysis
            lines = code.split('\n')
            loc = len([l for l in lines if l.strip()])

            return {
                "status": "ok",
                "language": language,
                "lines_of_code": loc,
                "total_lines": len(lines),
                "avg_line_length": sum(len(l) for l in lines) / max(len(lines), 1)
            }

    except Exception as e:
        return {"status": "error", "message": f"Code analysis error: {str(e)}"}


def _scientific_compute(args: Dict[str, Any]) -> Dict[str, Any]:
    """Advanced scientific computations"""
    try:
        computation = args.get("computation", "")

        if computation == "matrix":
            # Matrix operations
            import numpy as np
            matrix = np.array(args.get("matrix", []))
            operation = args.get("matrix_op", "determinant")

            if operation == "determinant":
                det = np.linalg.det(matrix)
                return {"status": "ok", "determinant": float(det)}

            elif operation == "inverse":
                inv = np.linalg.inv(matrix)
                return {"status": "ok", "inverse": inv.tolist()}

            elif operation == "eigenvalues":
                eigenvalues, eigenvectors = np.linalg.eig(matrix)
                return {
                    "status": "ok",
                    "eigenvalues": eigenvalues.tolist(),
                    "eigenvectors": eigenvectors.tolist()
                }

        elif computation == "integration":
            # Numerical integration
            from scipy import integrate

            # User provides function as string
            func_str = args.get("function", "")
            lower = args.get("lower_bound", 0)
            upper = args.get("upper_bound", 1)

            # Create function from string
            import math
            import numpy as np
            safe_dict = {
                'x': 0, 'math': math, 'np': np,
                'sin': math.sin, 'cos': math.cos, 'exp': math.exp,
                'log': math.log, 'sqrt': math.sqrt, 'pi': math.pi
            }

            def func(x):
                safe_dict['x'] = x
                return eval(func_str, {"__builtins__": {}}, safe_dict)

            result, error = integrate.quad(func, lower, upper)

            return {
                "status": "ok",
                "integral": float(result),
                "error_estimate": float(error),
                "bounds": [lower, upper]
            }

        elif computation == "differential":
            # Numerical differentiation
            from scipy.misc import derivative
            import math
            import numpy as np

            func_str = args.get("function", "")
            point = args.get("point", 0)

            safe_dict = {
                'x': 0, 'math': math, 'np': np,
                'sin': math.sin, 'cos': math.cos, 'exp': math.exp,
                'log': math.log, 'sqrt': math.sqrt, 'pi': math.pi
            }

            def func(x):
                safe_dict['x'] = x
                return eval(func_str, {"__builtins__": {}}, safe_dict)

            result = derivative(func, point, dx=1e-6)

            return {
                "status": "ok",
                "derivative": float(result),
                "point": point
            }

        else:
            return {"status": "error", "message": f"Unknown computation: {computation}"}

    except Exception as e:
        return {"status": "error", "message": f"Scientific computation error: {str(e)}"}


def _research_assist(args: Dict[str, Any]) -> Dict[str, Any]:
    """Research assistance and literature analysis"""
    try:
        task = args.get("task", "")

        if task == "citation":
            # Format citation
            authors = args.get("authors", [])
            title = args.get("title", "")
            year = args.get("year", "")
            journal = args.get("journal", "")
            style = args.get("style", "APA")

            if style.upper() == "APA":
                # APA format
                author_str = ", ".join(authors[:2])
                if len(authors) > 2:
                    author_str += ", et al."
                citation = f"{author_str} ({year}). {title}. {journal}."

            elif style.upper() == "MLA":
                # MLA format
                author_str = ", ".join(authors)
                citation = f"{author_str}. \"{title}.\" {journal}, {year}."

            else:
                citation = f"{', '.join(authors)}. {title}. {journal}, {year}."

            return {
                "status": "ok",
                "citation": citation,
                "style": style
            }

        elif task == "summarize":
            # Text summarization (basic)
            text = args.get("text", "")
            sentences = text.split('. ')
            summary_length = args.get("summary_length", 3)

            # Simple extractive summarization (take first N sentences)
            summary = '. '.join(sentences[:summary_length]) + '.'

            return {
                "status": "ok",
                "summary": summary,
                "original_length": len(sentences),
                "summary_length": summary_length
            }

        else:
            return {"status": "error", "message": f"Unknown research task: {task}"}

    except Exception as e:
        return {"status": "error", "message": f"Research assistance error: {str(e)}"}


def _ai_analysis(args: Dict[str, Any]) -> Dict[str, Any]:
    """AI-powered analysis using GPT-5.2 Pro"""
    try:
        from ..llm import answer as llm_answer

        content = args.get("content", "")
        analysis_type = args.get("analysis_type", "general")
        question = args.get("question", "")

        if not content and not question:
            return {"status": "error", "message": "No content or question provided"}

        # Build analysis prompt
        if analysis_type == "technical":
            system = "You are an expert technical analyst. Provide detailed technical analysis with specific insights, metrics, and recommendations."
        elif analysis_type == "scientific":
            system = "You are a scientific researcher. Analyze the content from a scientific perspective, identifying methods, findings, and implications."
        elif analysis_type == "code":
            system = "You are a senior software engineer. Analyze code for quality, efficiency, potential bugs, and improvements."
        elif analysis_type == "data":
            system = "You are a data scientist. Analyze data patterns, trends, anomalies, and provide statistical insights."
        else:
            system = "You are an analytical expert. Provide comprehensive, structured analysis with clear insights and actionable recommendations."

        if question:
            prompt = f"Content:\n{content}\n\nQuestion: {question}"
        else:
            prompt = f"Analyze the following:\n\n{content}"

        analysis = llm_answer(prompt, system=system)

        return {
            "status": "ok",
            "analysis": analysis,
            "analysis_type": analysis_type,
            "model": "GPT-5.2 Pro"
        }

    except Exception as e:
        return {"status": "error", "message": f"AI analysis error: {str(e)}"}


TOOL = Tool(
    name="analysis_ops",
    summary="Scientific and technical analysis - mathematics, statistics, code analysis, data analysis, research assistance, AI-powered insights using GPT-5.2 Pro",
    plan=_plan,
    run=_run,
)

register(TOOL)
