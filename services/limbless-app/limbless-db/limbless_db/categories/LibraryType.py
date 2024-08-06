from dataclasses import dataclass

from .ExtendedEnum import DBEnum, ExtendedEnum


@dataclass
class LibraryTypeEnum(DBEnum):
    abbreviation: str
    identifier: str
    modality: str

    @property
    def select_name(self) -> str:
        return self.abbreviation


class LibraryType(ExtendedEnum[LibraryTypeEnum], enum_type=LibraryTypeEnum):
    CUSTOM = LibraryTypeEnum(0, "Custom", "Custom", "Custom", "Custom")

    # 10X Base Technologies
    TENX_SC_GEX_FLEX = LibraryTypeEnum(1, "10X Single Cell Gene Expression Flex", "10X Flex", "10XFRP", "Gene Expression")
    TENX_SC_ATAC = LibraryTypeEnum(2, "10X Single Cell ATAC", "10X ATAC", "10XATAC", "Chromatin Accessibility")
    TENX_SC_GEX_3PRIME = LibraryTypeEnum(3, "10X Single Cell Gene Expression 3'", "10X 3'", "10XGEX3P", "Gene Expression")
    TENX_SC_GEX_5PRIME = LibraryTypeEnum(4, "10X Single Cell Immune Profiling 5'", "10X 5'", "10XGEX5P", "Gene Expression")

    # 10X Visium
    TENX_VISIUM_HD = LibraryTypeEnum(5, "10X HD Spatial Gene Expression", "10X HD Spatial", "10XVISIUMHD", "Spatial Transcriptomics")
    TENX_VISIUM_FFPE = LibraryTypeEnum(6, "10X Visium Gene Expression FFPE", "10X Visium FFPE", "10XVISIUMFFPE", "Spatial Transcriptomics")
    TENX_VISIUM = LibraryTypeEnum(7, "10X Visium Gene Expression", "10X Visium", "10XVISIUM", "Spatial Transcriptomics")
    
    # Optional 10X modalities
    TENX_ANTIBODY_CAPTURE = LibraryTypeEnum(8, "10X Antibody Capture", "10X Antibody Capture", "10XABC", "Antibody Capture")
    TENX_MULTIPLEXING_CAPTURE = LibraryTypeEnum(9, "10X Multiplexing Capture", "10X Multiplexing Capture", "10XHTO", "Multiplexing Capture")
    TENX_CRISPR_SCREENING = LibraryTypeEnum(10, "10X CRISPR Screening", "10X CRISPR Screening", "10XCRISPR", "CRISPR Screening")
    TENX_VDJ_B = LibraryTypeEnum(11, "10X VDJ B", "10X VDJ B", "10XVDJB", "VDJ-B")
    TENX_VDJ_T = LibraryTypeEnum(12, "10X VDJ T", "10X VDJ T", "10XVDJT", "VDJ-T")
    TENX_VDJ_T_GD = LibraryTypeEnum(13, "10X VDJ T GD", "10X VDJ T GD", "10XVDJTGD", "VDJ-T-GD")

    # RNA-seq
    POLY_A_RNA_SEQ = LibraryTypeEnum(101, "Poly-A RNA-Seq", "Poly-A RNA-Seq", "POLYARNA", "Gene Expression")
    SMART_SEQ = LibraryTypeEnum(102, "SMART-Seq", "SMART-Seq", "SMARTSEQ", "Gene Expression")
    SMART_SC_SEQ = LibraryTypeEnum(103, "SMART-Seq Single Cell", "SMART-Seq SC", "SMARTSEQSC", "Gene Expression")
    RIBO_DEPL_RNA_SEQ = LibraryTypeEnum(104, "Stranded RNA-Seq Ribosomal RNA Depletion", "Ribosomal RNA Depletion", "RRNADEPL", "Gene Expression")
    QUANT_SEQ = LibraryTypeEnum(105, "Transcriptome Fingerprinting 3' RNA-seq", "QUANT-seq", "QUANT", "Gene Expression")

    WGS = LibraryTypeEnum(106, "Whole Genome Sequencing", "WGS", "WGS", "Gene Expression")
    WES = LibraryTypeEnum(107, "Whole Exome Sequencing", "WES", "EXOME", "Gene Expression")
    ATAC_SEQ = LibraryTypeEnum(108, "ATAC-Seq", "ATAC-Seq", "ATAC", "Chromatin Accessibility")
    
    # EM
    RR_BS_SEQ = LibraryTypeEnum(109, "Reduced Representation Bisulfite Sequencing", "RR BS-Seq", "RRBS", "Methylation Profiling")
    WG_BS_SEQ = LibraryTypeEnum(110, "Whole Genome Bisulfite Sequencing", "WG BS-Seq", "WGBS", "Methylation Profiling")
    RR_EM_SEQ = LibraryTypeEnum(111, "Reduced Representation Enzymatic Methylation Sequencing", "RR EM-seq", "RREMSEQ", "Methylation Profiling")
    WG_EM_SEQ = LibraryTypeEnum(112, "Whole Genome Enzymatic Methylation Sequencing", "WG EM-Seq", "WGEM", "Methylation Profiling")

    ARTIC_SARS_COV_2 = LibraryTypeEnum(113, "ARTIC SARS-CoV-2", "ARTIC SARS-CoV-2", "ARTIC", "Viral Sequencing")
    IMMUNE_SEQ = LibraryTypeEnum(114, "Immune Sequencing", "Immune Sequencing", "IMMUNE", "Immune Sequencing")
    AMPLICON_SEQ = LibraryTypeEnum(115, "Amplicon-seq", "Amplicaon-seq", "AMPLICON", "Gene Expression")


identifiers = []
for t in LibraryType.as_list():
    if t.identifier in identifiers:
        raise ValueError(f"Duplicate LibraryType identifier: {t}")
    identifiers.append(t.identifier)
    