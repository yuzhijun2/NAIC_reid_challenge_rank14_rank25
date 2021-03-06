import os
import json
import cv2
import numpy as np

# Q_ROOT = "/data/xiangan/reid_data/testA/query_a"
# G_ROOT = "/data/xiangan/reid_data/testA/gallery_a"

Q_ROOT = "D:/reid_final/test_set/query_a/"
G_ROOT = "D:/reid_final/test_set/gallery_a/"

ranklist = "rerank_final_001.json"


def main():
    f = open(ranklist, encoding='utf-8')
    content = f.read()
    dic = json.loads(content)

    img_matrix = []
    for idx, query_name in enumerate(list(dic.keys())):
        img_row = []
        q = Q_ROOT + query_name
        img_q = cv2.imread(q)
        img_row.append(img_q)
        for gallery_name in dic[query_name][:10]:
            g = os.path.join(G_ROOT, gallery_name)
            img_g = cv2.imread(g)
            img_row.append(img_g)
        img_row = np.concatenate(img_row, axis=1)
        img_matrix.append(img_row)

        if idx != 0 and idx % 20 == 0:
            img_matrix = np.concatenate(img_matrix, axis=0)
            cv2.imwrite("bad_case_3/%d.png" % idx, img_matrix)
            img_matrix = []


if __name__ == '__main__':
    main()
