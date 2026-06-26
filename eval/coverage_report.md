# GrowthScout AI — Evaluation Dataset Coverage Report

This report is automatically generated to document coverage statistics, diversity metrics, and edge-case distributions across all golden evaluation datasets.

## 1. Golden Dataset Inventory
| Dataset | File | Cases | Dataset Version | Schema Version | Last Reviewed | Maintainer |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Discovery Dataset** | `discovery_dataset.json` | 30 | 1.1.0 | 1.0.0 | 2026-06-26 | Lead Evaluation Engineer |
| **Website Analysis Dataset** | `analysis_dataset.json` | 30 | 1.1.0 | 1.0.0 | 2026-06-26 | Lead Evaluation Engineer |
| **Recommendation Dataset** | `recommendation_dataset.json` | 30 | 1.1.0 | 1.0.0 | 2026-06-26 | Lead Evaluation Engineer |
| **Competitor Dataset** | `competitor_dataset.json` | 30 | 1.1.0 | 1.0.0 | 2026-06-26 | Lead Evaluation Engineer |
| **Opportunity Scoring Dataset** | `opportunity_scoring_dataset.json` | 30 | 1.1.0 | 1.0.0 | 2026-06-26 | Lead Evaluation Engineer |
| **Total Summary** | - | **150** | - | - | - | - |

## 2. Business Type (Industry) Diversity
| Business Type (Niche) | Case Count | Percentage |
| :--- | :--- | :--- |
| `dentist` | 38 | 25.3% |
| `pest_control` | 13 | 8.7% |
| `landscaper` | 9 | 6.0% |
| `house_cleaning` | 9 | 6.0% |
| `other` | 9 | 6.0% |
| `chiropractor` | 8 | 5.3% |
| `tax_prep` | 8 | 5.3% |
| `auto_repair` | 8 | 5.3% |
| `roofer` | 7 | 4.7% |
| `plumber` | 6 | 4.0% |
| `electrician` | 6 | 4.0% |
| `hvac` | 5 | 3.3% |
| `optometrist` | 4 | 2.7% |
| `veterinarian` | 4 | 2.7% |
| `tree_service` | 4 | 2.7% |
| `tutor` | 4 | 2.7% |
| `locksmith` | 3 | 2.0% |
| `painter` | 3 | 2.0% |
| `physiotherapy` | 2 | 1.3% |

## 3. Geographic Diversity
| City / Market | Case Count | Percentage |
| :--- | :--- | :--- |
| Global/Other | 120 | 80.0% |
| Austin | 2 | 1.3% |
| Seattle | 2 | 1.3% |
| Chicago | 2 | 1.3% |
| Boston | 2 | 1.3% |
| Denver | 2 | 1.3% |
| Phoenix | 2 | 1.3% |
| Philadelphia | 2 | 1.3% |
| Miami | 1 | 0.7% |
| Portland | 1 | 0.7% |
| Atlanta | 1 | 0.7% |
| Dallas | 1 | 0.7% |
| San Diego | 1 | 0.7% |
| Houston | 1 | 0.7% |
| Orlando | 1 | 0.7% |
| Nashville | 1 | 0.7% |
| Las Vegas | 1 | 0.7% |
| Minneapolis | 1 | 0.7% |
| San Jose | 1 | 0.7% |
| Charlotte | 1 | 0.7% |
| Detroit | 1 | 0.7% |
| Salt Lake City | 1 | 0.7% |
| St. Louis | 1 | 0.7% |
| Tampa | 1 | 0.7% |

## 4. Difficulty Distribution
| Difficulty Level | Case Count | Percentage |
| :--- | :--- | :--- |
| **Easy** | 101 | 67.3% |
| **Medium** | 40 | 26.7% |
| **Hard** | 9 | 6.0% |

## 5. Edge-Case & Scenario Distribution
| Edge-Case Scenario Category | Case Count |
| :--- | :--- |
| `no_website_business` | 6 |
| `robots_txt_blocked` | 5 |
| `limit_constraint` | 4 |
| `missing_metadata` | 3 |
| `missing_competitor_data` | 3 |
| `failed_audit` | 3 |
| `scraper_timeout` | 2 |
| `conflicting_competitor_signals` | 2 |
| `invalid_schema_markup` | 2 |
| `standard_pt_phoenix` | 2 |
| `standard_cleaning_philly` | 2 |
| `standard_auto_houston` | 2 |
| `standard_vet_orlando` | 2 |
| `standard_tax_nashville` | 2 |
| `standard_painters_vegas` | 2 |
| `standard_tree_minneapolis` | 2 |
| `standard_tutors_sanjose` | 2 |
| `standard_gym_charlotte` | 2 |
| `incomplete_audit_logs` | 2 |
| `standard_electricians_slc` | 2 |
| `standard_landscaping_tampa` | 2 |
| `standard_tax_phoenix` | 2 |
| `standard_chiropractor_miami` | 1 |
| `standard_plumber_austin` | 1 |
| `standard_dentist_seattle` | 1 |
| `standard_detail_denver` | 1 |
| `standard_dentist_austin` | 1 |
| `incomplete_seo_audit` | 1 |
| `website_timeout` | 1 |
| `missing_schema_markup` | 1 |

## 6. Manual vs. Synthesized Ratio
| Source Type | Case Count | Percentage |
| :--- | :--- | :--- |
| **Manual** | 125 | 83.3% |
| **Synthesized** | 25 | 16.7% |

## 7. Dataset Growth Statistics
| Sprint Created | Case Count | Contribution |
| :--- | :--- | :--- |
| `sprint_6.1` | 125 | 83.3% |
| `sprint_6.2` | 25 | 16.7% |