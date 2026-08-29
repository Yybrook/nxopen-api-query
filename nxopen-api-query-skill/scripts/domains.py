# -*- coding: utf-8 -*-
"""NXOpen 模块功能域映射表。

将 99 个顶层模块归入 12 个功能域，供 build_index.py 分组使用。
如需调整模块归属，直接修改本文件中的 DOMAINS 字典即可。

维护说明:
    - 新增模块时，将其添加到对应功能域的列表中
    - 未在 DOMAINS 中列出的模块会自动归入"其他"域
    - 模块名必须与 .pyi 文件名（去掉 .pyi 后缀）一致
    - 本文件与 nxopen-api-map/scripts/domains.py 保持一致
"""

# 功能域 → 模块名列表
DOMAINS = {
    "核心基础": [
        "NXOpen", "_nxopen", "Layer", "Display", "Select", "Fields",
        "Gateway", "Options", "Preferences", "Appearance",
    ],
    "建模与特征": [
        "Features", "GeometricUtilities", "Facet", "Implicit", "ModlDirect",
        "ModlUtils", "SheetMetal", "BodyDes", "StructureDesign", "RegionRecognition",
        "ShapeSearch", "Join", "Weld",
    ],
    "制图与标注": [
        "Drawings", "Drafting", "Annotations", "MBD", "TDP", "OpenXml", "Layout2d",
    ],
    "装配与产品数据": [
        "Assemblies", "PDM", "Positioning", "Placement", "DMU",
        "CollaborationApplication", "Issue", "Validate",
    ],
    "仿真分析": [
        "CAE", "SIM", "DesignSimulation", "CADCAEPrep", "GeometricAnalysis",
        "PressLineSimulation", "PhysMat",
    ],
    "制造加工": [
        "CAM", "Mfg", "MfgModel", "Tooling", "Die",
    ],
    "运动与机构": [
        "Motion", "Mechatronics", "AME",
    ],
    "电气与管路布线": [
        "Routing", "ElectricalRouting", "MechanicalRouting", "CableRouter",
        "RoutingCommon", "Formboard", "Schematic",
    ],
    "模具与复合材料": [
        "MoldCooling", "Falcon", "Composites", "Fabric", "Coatings",
    ],
    "编程与定制": [
        "UF", "BlockStyler", "UIStyler", "AutomatedTesting", "AutomatedTestingCase",
        "UserDefinedObjects", "UserDefinedTemplate", "MenuBar", "PartFamily",
    ],
    "报告与可视化": [
        "Report", "VisualReporting", "MendixReporting", "Markup",
    ],
    "行业专用": [
        "ShipDesign", "StageModel", "StageModelTemplate", "AnimationDesigner",
        "LineDesigner", "ToolDesigner", "PID", "PcbExchange", "Diagramming",
        "Safety", "ContactlessInspection", "DSE", "DSEDesignWorkflow", "DSEPlatform",
        "Optimization", "PLAS", "MPA", "CLDCommon", "CLDKin", "Newapp", "Rule",
        "AECDesign",
    ],
}

# 反向查找表：模块名 → 功能域名
mod_to_domain = {}
for _domain, _mods in DOMAINS.items():
    for _m in _mods:
        mod_to_domain[_m] = _domain
