# Successor Matrix

Derived directly from predecessor links in `scenario-complex-v30.json`.

## V1

| UID | Task Name | Predecessors | Successors |
| --- | --- | --- | --- |
| 1001 | Project Delivery Programme | - | - |
| 1002 | Enabling Works | - | - |
| 1003 | Site Mobilisation | - | 1004SS, 1005FS |
| 1004 | Temporary Utilities Setup | 1003SS | 1006FF |
| 1005 | Site Hoarding Installation | 1003FS | 1008FS |
| 1006 | Topographical Survey | 1004FF | 1008FS |
| 1007 | Substructure | - | - |
| 1008 | Bulk Excavation | 1005FS, 1006FS | 1009FS |
| 1009 | Pile Cap Construction | 1008FS | 1010FS |
| 1010 | Ground Beam Pour | 1009FS | 1011FS |
| 1011 | Basement Slab Pour | 1010FS | 1013SS, 1026SS |
| 1012 | Superstructure | - | - |
| 1013 | Ground Floor Frame Erection | 1011SS | 1014FS, 1015SS, 1016FS, 1018SS, 1019SS |
| 1014 | Level 1 Frame Erection | 1013FS | 1020SS |
| 1015 | Stair Core Construction | 1013SS | - |
| 1016 | Roof Steel Installation | 1013FS | 1025SS, 1028FS |
| 1017 | Services and Fit-Out | - | - |
| 1018 | Mechanical First Fix | 1013SS | 1021FS |
| 1019 | Electrical First Fix | 1013SS | 1021FS, 1028SF |
| 1020 | Fire Protection First Fix | 1014SS | 1029FF |
| 1021 | Internal Partitioning | 1018FS, 1019FS | 1022FS |
| 1022 | Drywall and Plaster | 1021FS | 1023FS |
| 1023 | Ceiling and Finishes | 1022FS | 1029FS |
| 1024 | External Works and Handover | - | - |
| 1025 | Facade Installation | 1016SS | 1029FS |
| 1026 | External Drainage | 1011SS | 1027FS |
| 1027 | Landscaping Works | 1026FS | - |
| 1028 | Lift Installation | 1016FS, 1019SF | 1029FS |
| 1029 | Commissioning and Testing | 1028FS, 1020FF, 1023FS, 1025FS | 1030FS |
| 1030 | Client Handover Documentation | 1029FS | - |

## V2

| UID | Task Name | Predecessors | Successors |
| --- | --- | --- | --- |
| 5001 | Project Delivery Programme | - | - |
| 5002 | Enabling Works | - | - |
| 5003 | Site Mobilisation | - | 5004SS, 5005FS |
| 5004 | Temporary Utilities Setup | 5003SS | 5006FF |
| 5005 | Site Hoarding Installation | 5003FS | 5008FS |
| 5006 | Utility Diversion Works | 5004FF | 5008FS |
| 5007 | Substructure | - | - |
| 5008 | Bulk Excavation | 5005FS, 5006FS | 5009FS |
| 5009 | Pile Cap Construction | 5008FS | 5010FS |
| 5010 | Ground Beam Pour | 5009FS | 5011FS |
| 5011 | Basement Slab Pour | 5010FS | 5013SS, 5026SS |
| 5012 | Superstructure | - | - |
| 5013 | Ground Floor Frame Erection | 5011SS | 5014FS, 5016FS, 5018SS, 5019SS |
| 5014 | Level 1 Frame Erection | 5013FS | 5015SS, 5020SS |
| 5015 | Prefabricated Riser Install | 5014SS | - |
| 5016 | Roof Steel Installation | 5013FS | 5025SS, 5028FS |
| 5017 | Services and Fit-Out | - | - |
| 5018 | Mechanical First Fix | 5013SS | 5021FS |
| 5019 | Electrical First Fix | 5013SS | 5021FS, 5028SF |
| 5020 | Fire Protection First Fix | 5014SS | 5029FF |
| 5021 | Internal Partitioning | 5018FS, 5019FS | 5022FS |
| 5022 | Drywall and Plaster | 5021FS | 5023FS |
| 5023 | Ceiling and Finishes | 5022FS | 5029FS |
| 5024 | External Works and Handover | - | - |
| 5025 | Facade Installation | 5016SS | 5029FS |
| 5026 | External Drainage | 5011SS | 5027FS |
| 5027 | Landscaping Works | 5026FS | - |
| 5028 | Lift Installation | 5016FS, 5019SF | 5029FS |
| 5029 | Commissioning and Testing | 5028FS, 5020FF, 5023FS, 5025FS | 5030FS |
| 5030 | Digital O&M Handover | 5029FS | - |
